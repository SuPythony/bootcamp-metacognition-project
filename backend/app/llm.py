"""OpenRouter client.

Reads LLM_MODEL_TUTOR and LLM_MODEL_CLASSIFIER from env. No model name is
hardcoded. `call_tutor` requests JSON-Schema-mode structured output and
retries once on parse failure with a corrective system message; a second
parse failure raises `LLMParseError` which the chat layer turns into a 502.

`stream_tutor` is intentionally a stub — SSE conversion is a staged follow-up
before frontend wiring begins.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# JSONL call logger
# ---------------------------------------------------------------------------

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("llm.calls")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter("%(message)s")

    # Ensure the logs directory exists.
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    fh = logging.FileHandler(logs_dir / "llm.jsonl", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def _logging_enabled() -> bool:
    """Return False when LOG_LLM_CALLS is set to a falsy value (false/0/no)."""
    return os.environ.get("LOG_LLM_CALLS", "true").lower() not in ("false", "0", "no")


def _write_log(entry: dict) -> None:
    if not _logging_enabled():
        return
    try:
        _setup_logger().debug(json.dumps(entry))
    except Exception:
        pass  # never let logging crash the caller


def mark_parse_result(session_id: str, success: bool, error: str | None = None) -> None:
    """Write a follow-up JSONL event recording the Pydantic parse outcome.

    Called by chat.py after AgentResponse.model_validate(). Fire-and-forget —
    never raises.
    """
    if not _logging_enabled():
        return
    entry: dict = {
        "event": "llm_parse_result",
        "ts":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": session_id,
        "parse_success": success,
    }
    if error is not None:
        entry["parse_error"] = error
    _write_log(entry)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

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
    temperature: float | None = None,
    timeout: float = 60.0,
    _max_retries: int = 4,
) -> dict:
    """Single POST to OpenRouter's chat-completions endpoint. Raises LLMError
    on non-2xx. Retries up to _max_retries times on 429, honouring Retry-After."""
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
    payload: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if response_format is not None:
        payload["response_format"] = response_format
    if temperature is not None:
        payload["temperature"] = temperature
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    url = f"{_base_url().rstrip('/')}/chat/completions"
    for attempt in range(_max_retries):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 429 and attempt < _max_retries - 1:
            wait = float(resp.headers.get("Retry-After", 2 ** attempt))
            await asyncio.sleep(min(wait, 30))
            continue
        if resp.status_code >= 400:
            raise LLMError(
                f"OpenRouter returned {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()
    raise LLMError("OpenRouter rate-limit: exhausted retries")


def _extract_content(response: dict) -> str:
    """Pull the assistant message content out of an OpenRouter response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected OpenRouter response shape: {response!r}") from e


def _strip_fences(text: str) -> str:
    """Extract JSON from a response that may contain markdown prose and code fences.

    Prefers the last ```json block (models often append JSON after explanation),
    then falls back to the last plain ``` block, then bare text.
    """
    matches = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if matches:
        return matches[-1]
    matches = re.findall(r"```[^\n]*\n(.*?)\n?```", text, re.DOTALL)
    if matches:
        return matches[-1]
    return text.strip()


def _extract_usage(response: dict) -> dict:
    """Pull token usage out of an OpenRouter response. Returns zeros if absent."""
    u = response.get("usage") or {}
    return {
        "prompt_tokens": int(u.get("prompt_tokens", 0)),
        "completion_tokens": int(u.get("completion_tokens", 0)),
        "total_tokens": int(u.get("total_tokens", 0)),
    }


async def call_tutor(
    messages: list[dict],
    schema: dict | None = None,
    session_id: str = "",
    temperature: float | None = None,
) -> tuple[dict, dict]:
    """Single tutor turn. Returns (parsed_output, token_usage).

    If `schema` is provided, requests JSON-Schema mode from OpenRouter and
    parses the response as JSON. On parse failure, retries once with an
    additional system message instructing the model to repair its output.
    token_usage shape: { prompt_tokens, completion_tokens, total_tokens }.
    """
    model = _env("LLM_MODEL_TUTOR")
    call_id = str(uuid.uuid4())
    t0 = time.monotonic()
    raw_content: str = ""

    response_format = (
        {"type": "json_schema", "json_schema": {"name": "tutor_turn", "schema": schema, "strict": True}}
        if schema is not None
        else {"type": "json_object"}
    )

    try:
        response = await _post_chat(
            model=model, messages=messages, response_format=response_format,
            temperature=temperature,
        )
        usage = _extract_usage(response)
        raw_content = _strip_fences(_extract_content(response))
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            _write_log({
                "event": "llm_call",
                "ts":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "call_id": call_id,
                "session_id": session_id,
                "model": model,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "input_tokens": usage["prompt_tokens"],
                "output_tokens": usage["completion_tokens"],
                "raw_output": raw_content,
                "parse_success": None,
            })
            return parsed, usage

        # Retry once with a corrective system note.
        retry_messages = messages + [
            {"role": "assistant", "content": raw_content},
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
            model=model, messages=retry_messages, response_format=response_format,
            temperature=temperature,
        )
        retry_usage = _extract_usage(response)
        combined_usage = {k: usage[k] + retry_usage[k] for k in usage}
        raw_content = _strip_fences(_extract_content(response))
        try:
            parsed = json.loads(raw_content)
            _write_log({
                "event": "llm_call",
                "ts":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "call_id": call_id,
                "session_id": session_id,
                "model": model,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "input_tokens": combined_usage["prompt_tokens"],
                "output_tokens": combined_usage["completion_tokens"],
                "raw_output": raw_content,
                "parse_success": None,
            })
            return parsed, combined_usage
        except json.JSONDecodeError as e:
            err = LLMParseError(
                f"Tutor output did not parse as JSON after one retry: {raw_content[:300]!r}"
            )
            _write_log({
                "event": "llm_error",
                "ts":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "call_id": call_id,
                "session_id": session_id,
                "model": model,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "input_tokens": combined_usage["prompt_tokens"],
                "output_tokens": combined_usage["completion_tokens"],
                "raw_output": raw_content,
                "parse_success": False,
                "error": str(err),
            })
            raise err from e

    except LLMError:
        raise
    except Exception as e:
        _write_log({
            "event": "llm_error",
            "ts":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id,
            "session_id": session_id,
            "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": 0,
            "output_tokens": 0,
            "raw_output": raw_content,
            "parse_success": False,
            "error": str(e),
        })
        raise


async def call_classifier(query: str, temperature: float | None = None) -> tuple[dict, dict]:
    """Domain classifier. Returns ({ "domain": str, "complexity_hint": str }, token_usage).

    The returned `domain` must be one of the user-facing domains registered in
    the plugin registry (i.e. not an internal domain). Validation is the
    caller's responsibility — this function just parses the model output.
    token_usage shape: { prompt_tokens, completion_tokens, total_tokens }.
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
        model=model, messages=messages, response_format=response_format,
        temperature=temperature,
    )
    usage = _extract_usage(response)
    content = _strip_fences(_extract_content(response))
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMParseError(
            f"Classifier output did not parse as JSON: {content[:200]!r}"
        ) from e

    # Some models return a bare JSON string ("math") instead of an object.
    if isinstance(parsed, str):
        parsed = {"domain": parsed}

    if parsed.get("domain") not in domains:
        raise LLMClassifierError(
            f"Classifier returned domain {parsed.get('domain')!r}, "
            f"which is not in {domains!r}"
        )
    parsed.setdefault("complexity_hint", "multi-step")
    return parsed, usage


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
