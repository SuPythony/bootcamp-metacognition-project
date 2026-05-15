"""Prompt variant registry.

Maps string keys like "base:v1" and "math:v1" to the Path of the corresponding
prompt file. `DEFAULTS` maps each role to its current default key. Three helper
functions cover the access patterns the codebase needs:

  load_prompt(role, variant_key=None) -> str
      Load a single prompt file by role. Pass variant_key to override the default.

  load_combined(domain, base_variant=None, domain_variant=None) -> str
      Load and concatenate the base + domain prompt — which is what every call
      site ultimately needs. Pass variant overrides to use non-default files.

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
    "base:v1":        _PROMPTS / "socratic_base.txt",
    "base:v2":        _PROMPTS / "socratic_base_v2.txt",
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


def load_prompt(role: str, variant_key: str | None = None) -> str:
    """Load a single prompt file by role name.

    Args:
        role: One of the keys in DEFAULTS ("base", "math", etc.).
        variant_key: Optional override. If None, uses DEFAULTS[role].

    Raises:
        KeyError: If role has no default and no variant_key is given.
        KeyError: If the resolved variant_key is not in VARIANTS.
        FileNotFoundError: If the mapped file does not exist on disk.
    """
    key = variant_key or DEFAULTS[role]
    path = VARIANTS[key]
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

    Equivalent to what chat.py and probes.py were doing manually:
        socratic_base + "\\n\\n" + domain_prompt

    Args:
        domain: Domain name — must match a key in DEFAULTS (e.g. "math").
        base_variant: Optional variant key for the base prompt.
        domain_variant: Optional variant key for the domain prompt.
    """
    base = load_prompt("base", variant_key=base_variant)
    domain_prompt = load_prompt(domain, variant_key=domain_variant)
    return base + "\n\n" + domain_prompt
