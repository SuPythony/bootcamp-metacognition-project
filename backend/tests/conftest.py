"""Shared pytest fixtures.

The backend package is installed via `pip install -e .` so `app` and
`specializations` are normally importable. This conftest adds the backend
folder to sys.path defensively in case tests are run without an editable
install.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def _reset_registry_and_sessions():
    """Ensure each test starts with empty registry and session store."""
    from app import plugin_registry, session as session_mod

    plugin_registry.reset_registry()
    session_mod.reset_store()
    yield
    plugin_registry.reset_registry()
    session_mod.reset_store()


@pytest.fixture
def loaded_registry():
    """Load the real specialization plugins from disk. Use for tests that
    verify the loader against the actual scaffold (math, programming, essay,
    science, general, persona)."""
    from app import plugin_registry

    plugin_registry.load_specializations()
    return plugin_registry


@pytest.fixture
def fake_openrouter(monkeypatch):
    """Mock the OpenRouter HTTP call. Yields a recorder you can configure.

    Usage:
        def test_x(fake_openrouter):
            fake_openrouter.responses = ['{"domain": "math", "complexity_hint": "multi-step"}']
            # ... call the LLM client ...
            assert fake_openrouter.requests[0]["model"] == "..."
    """
    from app import llm as llm_mod

    class Recorder:
        def __init__(self):
            self.requests: list[dict] = []
            self.responses: list[str] = []  # raw assistant message strings
            self.status_code = 200

        async def __call__(self, *, model, messages, response_format=None, timeout=60.0):
            self.requests.append(
                {
                    "model": model,
                    "messages": messages,
                    "response_format": response_format,
                }
            )
            if self.status_code >= 400:
                from app.llm import LLMError

                raise LLMError(f"mock {self.status_code}")
            if not self.responses:
                raise AssertionError(
                    "fake_openrouter has no more queued responses; "
                    f"call {len(self.requests)} not configured"
                )
            content = self.responses.pop(0)
            return {"choices": [{"message": {"content": content}}]}

    rec = Recorder()
    monkeypatch.setattr(llm_mod, "_post_chat", rec)
    # Provide harmless defaults so the env-var checks pass.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL_TUTOR", "test/tutor-model")
    monkeypatch.setenv("LLM_MODEL_CLASSIFIER", "test/classifier-model")
    return rec


@pytest.fixture
def tmp_persona_dir(tmp_path, monkeypatch):
    """Temp persona dir, exposed via PERSONA_DIR env var."""
    persona_dir = tmp_path / "personas"
    persona_dir.mkdir()
    monkeypatch.setenv("PERSONA_DIR", str(persona_dir))
    return persona_dir
