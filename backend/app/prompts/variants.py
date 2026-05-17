"""Prompt variant registry.

Maps string keys like "base:v1" and "math:v1" to prompt sources:
  - Base variants ("base:*") map to a **folder** containing multiple files
    assembled conditionally per turn by load_base_prompt().
  - Domain variants ("math:v1", etc.) map to individual prompt files as before.

`DEFAULTS` maps each role to its current default key. Four helper functions
cover the access patterns the codebase needs:

  load_base_prompt(variant_key=None, session=None, had_tool_result=False) -> str
      Assemble the base prompt from a variant folder. Conditionally appends
      phase and context blocks based on current session state.

  load_prompt(role, variant_key=None) -> str
      Load a single prompt file by role (domain roles only — raises for "base").

  load_combined(domain, base_variant=None, domain_variant=None) -> str
      Load and concatenate base + domain prompts. Used by probes (no session).

  parse_domain_variants(env_value) -> dict[str, str]
      Parse the PROMPT_VARIANT_DOMAIN env var format into a per-domain lookup.
      Format: comma-separated "<domain>:<version>" pairs, e.g.
          "math:v2,essay:v1,programming:v2"
      Returns a dict mapping domain name → full variant key, e.g.
          {"math": "math:v2", "essay": "essay:v1", "programming": "programming:v2"}
      Unknown domains are kept as-is so callers can surface the error.

Variant selection is static per process: callers read env vars at startup and
pass the result here. This module has no env-var awareness — that stays in the
callers (chat.py for the live app, run_probes.py for the probe runner).
"""

from __future__ import annotations

from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent.parent  # backend/
_PROMPTS = _BACKEND / "app" / "prompts"
_SPECS = _BACKEND / "specializations"

VARIANTS: dict[str, Path] = {
    # Base variants map to folders; files within are assembled per-turn.
    "base:v1":        _PROMPTS / "v1",
    # Domain variants — flat files, unchanged.
    "math:v1":        _SPECS / "math" / "prompt.txt",
    "math:v2":        _SPECS / "math" / "prompt_v2.txt",
    "programming:v1": _SPECS / "programming" / "prompt.txt",
    "essay:v1":       _SPECS / "essay" / "prompt.txt",
    "general:v1":     _SPECS / "general" / "prompt.txt",
    "science:v1":     _SPECS / "science" / "prompt.txt",
    "persona:v1":     _SPECS / "persona" / "prompt.txt",
}

DEFAULTS: dict[str, str] = {
    "base":        "base:v1",
    "math":        "math:v1",
    "programming": "programming:v1",
    "essay":       "essay:v1",
    "general":     "general:v1",
    "science":     "science:v1",
    "persona":     "persona:v1",
}


def _maybe_append(blocks: list[str], path: Path) -> None:
    if path.exists():
        blocks.append(path.read_text(encoding="utf-8"))


def load_base_prompt(
    variant_key: str | None = None,
    session: object = None,
    had_tool_result: bool = False,
) -> str:
    """Assemble the base prompt from a variant folder.

    Always includes core.txt. Conditionally appends one phase block and up to
    three context blocks based on session state. When session is None (e.g. in
    probe runs) only core.txt is returned.

    Args:
        variant_key: Key into VARIANTS (must resolve to a folder). Defaults to
                     DEFAULTS["base"].
        session: Live Session object. Used to derive phase and context flags.
                 Pass None when no session is available (probes, tests).
        had_tool_result: True when the current /chat request carried a
                         tool_result body field (frontend tool returning data).
    """
    key = variant_key or DEFAULTS["base"]
    folder = VARIANTS[key]
    if not folder.is_dir():
        raise KeyError(
            f"Variant {key!r} must map to a folder. Got: {folder}. "
            "For base variants, VARIANTS must point at a directory."
        )

    blocks = [(folder / "core.txt").read_text(encoding="utf-8")]

    # Phase block — one file per phase, named phase_<phase>.txt.
    phase = getattr(session, "phase", None)
    if phase is not None:
        _maybe_append(blocks, folder / f"phase_{phase}.txt")

    # Tool-result block — injected when this turn's request carried tool output.
    if had_tool_result:
        _maybe_append(blocks, folder / "block_tool_result.txt")

    # Calibration block — injected during the solving phase always (so the model
    # can emit emit_calibration_check without a chicken-and-egg dependency), and
    # also whenever an open CalibrationPoint exists (outcome not yet recorded).
    calibration_pts = getattr(session, "calibration_points", [])
    if phase == "solving" or any(cp.outcome is None for cp in calibration_pts):
        _maybe_append(blocks, folder / "block_calibration.txt")

    # Reflection-eval block — injected when the pending reflection has a student
    # response but the quality evaluation hasn't arrived yet.
    pending_idx = getattr(session, "pending_reflection_index", None)
    reflection_list = getattr(session, "reflection_prompts", [])
    if (
        pending_idx is not None
        and pending_idx < len(reflection_list)
        and reflection_list[pending_idx].response is not None
        and reflection_list[pending_idx].quality is None
    ):
        _maybe_append(blocks, folder / "block_reflection_eval.txt")

    return "\n\n".join(blocks)


def load_prompt(role: str, variant_key: str | None = None) -> str:
    """Load a single prompt file by role name (domain roles only).

    Do NOT call with role="base" — use load_base_prompt() instead. Raises
    RuntimeError if called for the base role to surface this at startup.

    Args:
        role: One of the domain keys in DEFAULTS ("math", "essay", etc.).
        variant_key: Optional override. If None, uses DEFAULTS[role].

    Raises:
        RuntimeError: If role == "base".
        KeyError: If role has no default and no variant_key is given.
        KeyError: If the resolved variant_key is not in VARIANTS.
        KeyError: If the resolved path is a directory (base variant key misused).
        FileNotFoundError: If the mapped file does not exist on disk.
    """
    if role == "base":
        raise RuntimeError(
            "load_prompt('base') is deprecated. "
            "Call load_base_prompt(variant_key=..., session=...) instead."
        )
    key = variant_key or DEFAULTS[role]
    path = VARIANTS[key]
    if path.is_dir():
        raise KeyError(
            f"Variant {key!r} for role {role!r} resolves to a directory. "
            "Domain variants must be files."
        )
    return path.read_text(encoding="utf-8")


def parse_domain_variants(env_value: str) -> dict[str, str]:
    """Parse PROMPT_VARIANT_DOMAIN into a per-domain variant key map.

    Args:
        env_value: Comma-separated "<domain>:<version>" pairs, e.g.
                   "math:v2,essay:v1,programming:v2".

    Returns:
        Dict mapping domain name → full VARIANTS key, e.g.
        {"math": "math:v2", "essay": "essay:v1"}.
        Empty string or whitespace-only input returns {}.
    """
    result: dict[str, str] = {}
    for entry in env_value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(
                f"Invalid PROMPT_VARIANT_DOMAIN entry {entry!r}: "
                "expected '<domain>:<version>' (e.g. 'math:v2')."
            )
        domain, _, version = entry.rpartition(":")
        result[domain] = f"{domain}:{version}"
    return result


def load_combined(
    domain: str,
    base_variant: str | None = None,
    domain_variant: str | None = None,
) -> str:
    """Load and concatenate base + domain prompts.

    The base is assembled via load_base_prompt(session=None), so only core.txt
    is included (no per-session conditional blocks). This is appropriate for
    probe runs and tests that have no live session.

    Args:
        domain: Domain name — must match a key in DEFAULTS (e.g. "math").
        base_variant: Optional variant key for the base prompt folder.
        domain_variant: Optional variant key for the domain prompt file.
    """
    base = load_base_prompt(variant_key=base_variant, session=None)
    domain_prompt = load_prompt(domain, variant_key=domain_variant)
    return base + "\n\n" + domain_prompt
