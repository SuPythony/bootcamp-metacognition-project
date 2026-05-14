"""OpenRouter client.

Reads LLM_MODEL_TUTOR and LLM_MODEL_CLASSIFIER from env. No model name is
hardcoded. `call_tutor` requests JSON-Schema-mode structured output and
retries once on parse failure with a corrective system message; a second
parse failure raises `LLMParseError` which the chat layer turns into a 502.

`stream_tutor` is intentionally a stub — SSE conversion is a staged follow-up
before frontend wiring begins.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


class LLMError(RuntimeError):
    """Base for any LLM failure: HTTP, parse, validation."""


class LLMParseError(LLMError):
    """The model's output did not parse as JSON after one retry."""


class LLMClassifierError(LLMError):
    """Classifier returned a domain not registered in the plugin registry."""


def _env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise LLMError(f"Required env var {name!r} is not set")
    return val


def _base_url() -> str:
    return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def _api_key() -> str:
    return _env("OPENROUTER_API_KEY")


async def _post_chat(
    *,
    model: str,
    messages: list[dict],
    response_format: dict | None = None,
    timeout: float = 60.0,
) -> dict:
    """Single POST to OpenRouter's chat-completions endpoint. Raises LLMError
    on non-2xx. Returns the parsed JSON body."""
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if response_format is not None:
        payload["response_format"] = response_format
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    url = f"{_base_url().rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        raise LLMError(
            f"OpenRouter returned {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def _extract_content(response: dict) -> str:
    """Pull the assistant message content out of an OpenRouter response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected OpenRouter response shape: {response!r}") from e


async def call_tutor(
    messages: list[dict],
    schema: dict | None = None,
) -> dict:
    """Single tutor turn. Returns the parsed structured-output dict.

    If `schema` is provided, requests JSON-Schema mode from OpenRouter and
    parses the response as JSON. On parse failure, retries once with an
    additional system message instructing the model to repair its output.
    """
    model = _env("LLM_MODEL_TUTOR")
    response_format = (
        {"type": "json_schema", "json_schema": {"name": "tutor_turn", "schema": schema, "strict": True}}
        if schema is not None
        else {"type": "json_object"}
    )

    response = await _post_chat(
        model=model, messages=messages, response_format=response_format
    )
    content = _extract_content(response)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Retry once with a corrective system note.
    retry_messages = messages + [
        {
            "role": "assistant",
            "content": content,
        },
        {
            "role": "system",
            "content": (
                "Your previous reply was not valid JSON matching the required "
                "schema. Reply again with a single JSON object only — no prose, "
                "no markdown fences, no commentary."
            ),
        },
    ]
    response = await _post_chat(
        model=model, messages=retry_messages, response_format=response_format
    )
    content = _extract_content(response)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMParseError(
            f"Tutor output did not parse as JSON after one retry: {content[:300]!r}"
        ) from e


async def call_classifier(query: str) -> dict:
    """Domain classifier. Returns { "domain": str, "complexity_hint": str }.

    The returned `domain` must be one of the user-facing domains registered in
    the plugin registry (i.e. not an internal domain). Validation is the
    caller's responsibility — this function just parses the model output.
    """
    model = _env("LLM_MODEL_CLASSIFIER")
    # Build a tight system prompt that constrains output to JSON.
    # Domain list is supplied at call time rather than baked in, so adding
    # a new specialization auto-flows through here without code edits.
    from app import plugin_registry  # local import — avoids circularity at module load

    domains = [d for d in plugin_registry.list_domains() if not plugin_registry.is_internal(d)]
    if not domains:
        raise LLMError(
            "No specializations registered — call_classifier cannot validate output."
        )

    system = (
        "Classify the student's query into exactly one of these subject domains: "
        + ", ".join(domains)
        + ". Also estimate complexity: single-step | multi-step | open-ended. "
        + 'Reply with one JSON object: {"domain": "<one of the listed>", "complexity_hint": "<one of: single-step, multi-step, open-ended>"}. '
        + "No prose, no markdown, no extra fields."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": query},
    ]
    response_format = {"type": "json_object"}
    response = await _post_chat(
        model=model, messages=messages, response_format=response_format
    )
    content = _extract_content(response)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMParseError(
            f"Classifier output did not parse as JSON: {content[:200]!r}"
        ) from e

    if parsed.get("domain") not in domains:
        raise LLMClassifierError(
            f"Classifier returned domain {parsed.get('domain')!r}, "
            f"which is not in {domains!r}"
        )
    parsed.setdefault("complexity_hint", "multi-step")
    return parsed


async def stream_tutor(
    messages: list[dict],
    schema: dict | None = None,
):
    """Streaming tutor — async generator yielding ('token', chunk) for reply
    deltas and ('state', dict) once with the validated control object.

    Intentionally a stub: SSE is a staged follow-up. Wiring SSE in the chat
    layer should land alongside the implementation of this generator.
    """
    raise NotImplementedError(
        "Streaming is staged for a follow-up commit; use call_tutor in v1."
    )
