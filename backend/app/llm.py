"""OpenRouter client.

Reads LLM_MODEL_TUTOR and LLM_MODEL_CLASSIFIER from env. No model name is
hardcoded anywhere in the app. Returns structured output per the JSON schema
documented in the Socratic base prompt; falls back to JSON mode + Pydantic
parsing with a single retry on parse failure.
"""

import os

OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)


async def call_tutor(messages: list[dict], schema: dict | None = None) -> dict:
    """Single tutor turn. Returns the parsed structured-output object."""
    raise NotImplementedError


async def stream_tutor(messages: list[dict], schema: dict | None = None):
    """Async generator yielding ('token', str) for reply chunks and
    ('state', dict) once with the validated control object."""
    raise NotImplementedError


async def call_classifier(query: str) -> dict:
    """Returns { domain, complexity_hint } using the cheap classifier model."""
    raise NotImplementedError
