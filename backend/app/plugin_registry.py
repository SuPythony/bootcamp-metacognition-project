"""Folder-scanning loader for specializations.

On startup, scans backend/specializations/*/manifest.json and registers each
domain. Provides:
  - get_prompt(domain) -> str   (Socratic base + domain prompt.txt)
  - get_manifest(domain) -> dict
  - dispatch_tool(domain, tool_name, args, session) -> dict   (routes /tools/{name})
  - get_specializations() -> list[dict]   (powers GET /specializations)
"""

from pathlib import Path

SPECIALIZATIONS_DIR = Path(__file__).resolve().parent.parent / "specializations"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_REGISTRY: dict[str, dict] = {}


def load_specializations() -> None:
    """Scan SPECIALIZATIONS_DIR and populate _REGISTRY. Called at app startup."""
    raise NotImplementedError


def register_specialization(domain: str, prompt_file: str, tools: list[str]) -> None:
    """Called by each specialization's __init__.py."""
    raise NotImplementedError


def get_prompt(domain: str) -> str:
    """Return SOCRATIC_BASE + '\\n\\n' + the domain's prompt.txt."""
    raise NotImplementedError


def get_manifest(domain: str) -> dict:
    raise NotImplementedError


def dispatch_tool(domain: str, tool_name: str, args: dict, session) -> dict:
    raise NotImplementedError


def get_specializations() -> list[dict]:
    """Public discovery payload for GET /specializations."""
    raise NotImplementedError
