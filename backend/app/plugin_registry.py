"""Folder-scanning loader for specialization plugins.

On startup, `load_specializations()` imports each package under
backend/specializations/. Each package's `__init__.py` calls
`register_specialization(...)` at import time, populating the in-memory
registry. The plugin's `manifest.json` is the source of truth for the tool
list and execution routing.

Tool dispatch (`dispatch_tool`) is keyed off `manifest.tools[].execution`:
- "backend": imports `specializations.<domain>.tools.<tool_name>` and calls
  its `run(args, session)` function.
- "frontend": returns a sentinel describing the call; the chat layer surfaces
  this to the client (eventually as an SSE `frontend_tool` event) and replays
  the result back on the next `/chat` turn.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

SPECIALIZATIONS_DIR = Path(__file__).resolve().parent.parent / "specializations"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Registry shape:
#   _REGISTRY[domain] = {
#       "folder": Path,
#       "manifest": dict (from manifest.json),
#       "prompt": str (raw domain prompt.txt contents),
#   }
_REGISTRY: dict[str, dict] = {}

_BASE_PROMPT: str | None = None


def _load_base_prompt() -> str:
    global _BASE_PROMPT
    if _BASE_PROMPT is None:
        _BASE_PROMPT = (PROMPTS_DIR / "socratic_base.txt").read_text()
    return _BASE_PROMPT


def register_specialization(domain: str, prompt_file: str, tools: list[str]) -> None:
    """Called by each specialization's `__init__.py` at import time.

    Args:
        domain: the domain key (must match `manifest.json["domain"]`).
        prompt_file: pass `__file__` from the specialization's `__init__.py`;
            the folder is derived from this.
        tools: list of tool names declared by this specialization. Must match
            the tool names in `manifest.json` exactly. Mismatch raises.
    """
    if domain in _REGISTRY:
        raise ValueError(f"Domain {domain!r} is already registered")

    folder = Path(prompt_file).resolve().parent
    manifest_path = folder / "manifest.json"
    prompt_path = folder / "prompt.txt"

    if not manifest_path.exists():
        raise FileNotFoundError(f"{manifest_path} missing for domain {domain!r}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"{prompt_path} missing for domain {domain!r}")

    manifest = json.loads(manifest_path.read_text())
    prompt = prompt_path.read_text()

    if manifest.get("domain") != domain:
        raise ValueError(
            f"Manifest domain {manifest.get('domain')!r} does not match "
            f"register_specialization argument {domain!r}"
        )

    manifest_tool_names = {t["name"] for t in manifest.get("tools", [])}
    declared = set(tools)
    if manifest_tool_names != declared:
        raise ValueError(
            f"Specialization {domain!r}: tools declared in __init__.py "
            f"{sorted(declared)!r} do not match manifest tools "
            f"{sorted(manifest_tool_names)!r}"
        )

    for tool in manifest.get("tools", []):
        if tool.get("execution") not in {"backend", "frontend"}:
            raise ValueError(
                f"Tool {tool.get('name')!r} in {domain!r} must declare "
                f"`execution: 'backend' | 'frontend'` (got {tool.get('execution')!r})"
            )
        if tool["execution"] == "frontend" and not tool.get("frontend_handler"):
            raise ValueError(
                f"Frontend tool {tool['name']!r} in {domain!r} must declare "
                f"`frontend_handler`"
            )

    _REGISTRY[domain] = {"folder": folder, "manifest": manifest, "prompt": prompt}


def load_specializations() -> None:
    """Scan SPECIALIZATIONS_DIR, import each package to trigger registration.

    Idempotent across calls — resets the registry before scanning so that
    test fixtures and reloads behave predictably.
    """
    global _BASE_PROMPT
    _REGISTRY.clear()
    _BASE_PROMPT = None  # invalidate cached base prompt so edits are picked up
    for child in sorted(SPECIALIZATIONS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(("_", ".")):
            continue
        if not (child / "__init__.py").exists():
            continue
        module_name = f"specializations.{child.name}"
        # Force re-import so registration runs even if the module was previously
        # imported in this process (e.g. by an earlier test).
        if module_name in importlib.sys.modules:
            del importlib.sys.modules[module_name]
        importlib.import_module(module_name)


def get_prompt(domain: str) -> str:
    """Return the full system prompt for a domain: Socratic base + domain prompt."""
    if domain not in _REGISTRY:
        raise KeyError(f"Unknown domain: {domain!r}")
    return _load_base_prompt() + "\n\n" + _REGISTRY[domain]["prompt"]


def get_manifest(domain: str) -> dict:
    if domain not in _REGISTRY:
        raise KeyError(f"Unknown domain: {domain!r}")
    return _REGISTRY[domain]["manifest"]


def get_specializations() -> list[dict]:
    """Public-facing discovery payload for `GET /specializations`.

    Excludes specializations whose manifest declares `internal: true`
    (e.g. the persona onboarding domain — never user-selectable).
    """
    return [
        {
            "domain": m["manifest"]["domain"],
            "display_name": m["manifest"].get(
                "display_name", m["manifest"]["domain"].title()
            ),
            "tools": m["manifest"].get("tools", []),
            "ui_components": m["manifest"].get("ui_components", []),
        }
        for m in _REGISTRY.values()
        if not m["manifest"].get("internal")
    ]


def list_domains(include_internal: bool = True) -> list[str]:
    """All registered domain names. Used by classifier output validation."""
    return [
        d
        for d, m in _REGISTRY.items()
        if include_internal or not m["manifest"].get("internal")
    ]


def is_internal(domain: str) -> bool:
    """True if the domain is marked `internal: true` in its manifest."""
    if domain not in _REGISTRY:
        return False
    return bool(_REGISTRY[domain]["manifest"].get("internal"))


def dispatch_tool(
    domain: str, tool_name: str, args: dict, session: Any
) -> dict:
    """Route a tool call. Returns either a backend tool's result (with
    `execution: "backend"`) or a sentinel describing a frontend tool the
    caller must surface to the client.

    Backend tools must export a `run(args, session) -> dict` function that
    returns at least `{ "result": ..., "ui_component": ..., "display_data": ... }`.
    """
    if domain not in _REGISTRY:
        raise KeyError(f"Unknown domain: {domain!r}")
    manifest = _REGISTRY[domain]["manifest"]
    tool_entry = next(
        (t for t in manifest.get("tools", []) if t["name"] == tool_name), None
    )
    if tool_entry is None:
        raise KeyError(f"Tool {tool_name!r} not registered for domain {domain!r}")

    if tool_entry["execution"] == "frontend":
        return {
            "execution": "frontend",
            "name": tool_name,
            "args": args,
            "frontend_handler": tool_entry["frontend_handler"],
            "ui_component": tool_entry.get("ui_component"),
        }

    module = importlib.import_module(
        f"specializations.{domain}.tools.{tool_name}"
    )
    if not hasattr(module, "run"):
        raise RuntimeError(
            f"Backend tool {domain}.{tool_name} does not export a run() function"
        )
    result = module.run(args, session)
    if not isinstance(result, dict) or "result" not in result:
        raise RuntimeError(
            f"Tool {domain}.{tool_name} run() must return a dict with a 'result' key; got {type(result).__name__}"
        )
    return {
        "execution": "backend",
        "name": tool_name,
        "ui_component": tool_entry.get("ui_component"),
        **result,
    }


def reset_registry() -> None:
    """Clear the registry. Test helper; not used in production code."""
    _REGISTRY.clear()
