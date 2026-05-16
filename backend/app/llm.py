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
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
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
            _user_preview = next(
                (m["content"][:300] for m in reversed(messages) if m.get("role") == "user"),
                None,
            )
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
                "user_message_preview": _user_preview,
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
            _user_preview = next(
                (m["content"][:300] for m in reversed(messages) if m.get("role") == "user"),
                None,
            )
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
                "user_message_preview": _user_preview,
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


async def call_classifier(
    query: str,
    temperature: float | None = None,
    session_id: str = "classifier",
) -> tuple[dict, dict]:
    """Domain classifier. Returns ({ "domain": str, "complexity_hint": str }, token_usage).

    The returned `domain` must be one of the user-facing domains registered in
    the plugin registry (i.e. not an internal domain). Validation is the
    caller's responsibility — this function just parses the model output.
    token_usage shape: { prompt_tokens, completion_tokens, total_tokens }.
    """
    model = _env("LLM_MODEL_CLASSIFIER")
    call_id = str(uuid.uuid4())
    t0 = time.monotonic()
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
    try:
        response = await _post_chat(
            model=model, messages=messages, response_format=response_format,
            temperature=temperature,
        )
        usage = _extract_usage(response)
        content = _strip_fences(_extract_content(response))
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            _write_log({
                "event": "llm_classifier_error",
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "call_id": call_id, "session_id": session_id, "model": model,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "query": query, "error": f"JSON parse error: {e}",
            })
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
        _write_log({
            "event": "llm_classifier",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id, "session_id": session_id, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
            "query": query, "result": parsed,
        })
        return parsed, usage
    except (LLMError, LLMParseError, LLMClassifierError):
        raise
    except Exception as e:
        _write_log({
            "event": "llm_classifier_error",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id, "session_id": session_id, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": 0, "output_tokens": 0,
            "query": query, "error": str(e),
        })
        raise


async def call_summarizer(
    initial_understanding: str | None,
    recent_student_messages: list[str],
    temperature: float = 0.3,
    session_id: str = "summarizer",
) -> dict:
    """Generate final_understanding + delta label for the thinking trace.

    Returns a dict with keys: final_understanding (str), delta_label (str),
    delta_evidence (str). On any failure, returns safe fallback strings.
    """
    model = _env("LLM_MODEL_CLASSIFIER")  # cheap model is fine for this task
    student_block = "\n".join(f"- {m}" for m in recent_student_messages[-4:]) or "(none)"
    initial_block = initial_understanding or "(not captured)"
    system = (
        "You are writing a warm, concise wrap-up reflection for a student who just "
        "finished a Socratic tutoring session. You are speaking TO the student.\n\n"
        "Respond with exactly one JSON object — no prose, no markdown — with these keys:\n"
        '  "final_understanding": one sentence addressed to the student in second person ("you"), '
        "describing what they now understand. Start with a verb like \"You came to see\", "
        "\"You worked out\", \"You can now explain\". Describe what they grasped, not what they missed.\n"
        '  "delta_label": exactly one of "significant", "moderate", "small" — how much their understanding grew.\n'
        '  "delta_evidence": one sentence in second person describing the shift, e.g. '
        "\"You moved from … to …\". Concrete, evidence-based, no judgement.\n\n"
        "Hard constraints:\n"
        "- Never use third person (\"the student\"). Always address them as \"you\".\n"
        "- Never grade. Do not say their understanding is \"fragmented\", \"incomplete\", "
        "\"partial\", \"shallow\", or that it \"does not show\" something.\n"
        "- Focus on what they grasped, not on what they missed.\n"
        "- Base your answer only on the provided messages."
    )
    user = (
        f"Initial understanding: {initial_block}\n\n"
        f"Recent student messages (most recent last):\n{student_block}"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    call_id = str(uuid.uuid4())
    t0 = time.monotonic()
    try:
        response = await _post_chat(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        usage = _extract_usage(response)
        content = _strip_fences(_extract_content(response))
        parsed = json.loads(content)
        result = {
            "final_understanding": str(parsed.get("final_understanding", "")),
            "delta_label": str(parsed.get("delta_label", "small")),
            "delta_evidence": str(parsed.get("delta_evidence", "")),
        }
        _write_log({
            "event": "llm_summarizer",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id, "session_id": session_id, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
            "result": result,
        })
        return result
    except Exception as exc:  # noqa: BLE001
        _write_log({
            "event": "llm_summarizer_error",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id, "session_id": session_id, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": 0, "output_tokens": 0,
            "error": str(exc),
        })
        logging.getLogger("app.llm").warning("call_summarizer failed: %s", exc)
        return {
            "final_understanding": None,
            "delta_label": None,
            "delta_evidence": None,
        }


async def call_initial_understanding_summarizer(
    clarification_student_messages: list[str],
    temperature: float = 0.3,
    session_id: str = "initial_summarizer",
) -> str | None:
    """Synthesise initial_understanding from the student's clarification-phase
    messages. Mirror of call_summarizer but only produces a single sentence
    capturing what the student understood at the start of the session.

    Returns the one-sentence string, or None on failure / empty input.
    """
    if not clarification_student_messages:
        return None
    model = _env("LLM_MODEL_CLASSIFIER")  # cheap model is fine for this task
    student_block = "\n".join(f"- {m}" for m in clarification_student_messages[-6:])
    system = (
        "You are writing a one-sentence opening for a Socratic tutoring "
        "session's thinking trace. The student has just finished the "
        "clarification phase — you are summarising what they understood at "
        "the start, before any guided work happened. You are speaking TO the student.\n\n"
        "Respond with exactly one JSON object — no prose, no markdown — with this key:\n"
        '  "initial_understanding": one sentence addressed to the student in second person ("you"). '
        "Start with \"You came in thinking\", \"You started by\", or \"At the start, you\". "
        "Capture their starting framing or gut take, even if it was partial or "
        "\"I have no idea where to start\" — that is still a valid starting point. "
        "Describe what they brought to the table, not what they were missing.\n\n"
        "Hard constraints:\n"
        "- Never use third person (\"the student\"). Always \"you\".\n"
        "- Never grade. Do not call their starting point \"wrong\", \"incomplete\", "
        "\"fragmented\", or \"shallow\".\n"
        "- Base your answer only on the provided messages."
    )
    user = f"Student messages during clarification (most recent last):\n{student_block}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    call_id = str(uuid.uuid4())
    t0 = time.monotonic()
    try:
        response = await _post_chat(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        usage = _extract_usage(response)
        content = _strip_fences(_extract_content(response))
        parsed = json.loads(content)
        result = str(parsed.get("initial_understanding", "")).strip() or None
        _write_log({
            "event": "llm_initial_summarizer",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id, "session_id": session_id, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
            "result": result,
        })
        return result
    except Exception as exc:  # noqa: BLE001
        _write_log({
            "event": "llm_initial_summarizer_error",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "call_id": call_id, "session_id": session_id, "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "input_tokens": 0, "output_tokens": 0,
            "error": str(exc),
        })
        logging.getLogger("app.llm").warning("call_initial_understanding_summarizer failed: %s", exc)
        return None


class _ReplyExtractor:
    """State machine that extracts the 'reply' string value from streaming JSON.

    The model emits one JSON object whose content streams token-by-token.
    Structure is always: { "thinking": "...", "reply": "...", "control": ..., "signal": ... }
    We scan for the "reply" key, then emit each character inside its string value.

    Handles JSON escape sequences (\n, \t, \\, \", ...) and gracefully ignores
    false positives (e.g. "reply" inside the thinking string is escaped as
    \"reply\" which fails the colon-check and resets the state).
    """

    def __init__(self) -> None:
        self._state = "scan"   # scan → colon → open_quote → value → done
        self._buf = ""
        self._esc = False

    def feed(self, chunk: str) -> str:
        out: list[str] = []
        for c in chunk:
            if self._state == "scan":
                self._buf += c
                if len(self._buf) > 200:
                    self._buf = self._buf[-200:]
                if self._buf.endswith('"reply"'):
                    self._state = "colon"
                    self._buf = ""
            elif self._state == "colon":
                if c == ":":
                    self._state = "open_quote"
                elif c in " \t\n\r":
                    pass
                else:
                    # False positive (e.g. \"reply\" inside a string value) — reset.
                    self._state = "scan"
                    self._buf = '"reply"' + c
            elif self._state == "open_quote":
                if c == '"':
                    self._state = "value"
                elif c in " \t\n\r":
                    pass
                elif c == "n":
                    # "null" reply
                    self._state = "done"
                else:
                    self._state = "scan"
                    self._buf = c
            elif self._state == "value":
                if self._esc:
                    _MAP = {
                        "n": "\n", "t": "\t", "r": "\r", '"': '"',
                        "\\": "\\", "/": "/", "b": "\b", "f": "\f",
                    }
                    out.append(_MAP.get(c, c))
                    self._esc = False
                elif c == "\\":
                    self._esc = True
                elif c == '"':
                    self._state = "done"
                else:
                    out.append(c)
            # done: consume silently
        return "".join(out)


async def stream_tutor(
    messages: list[dict],
    schema: dict | None = None,
    session_id: str = "",
    temperature: float | None = None,
):
    """Streaming tutor turn — async generator yielding:
      ('token', str)   — reply text chunks as they arrive from the model
      ('state', dict)  — the full parsed JSON once the stream is complete
      ('error', str)   — if the HTTP call or JSON parse fails (no 'state' follows)

    The 'thinking' field is buffered server-side and never forwarded.
    Token events are emitted only for characters inside the 'reply' value;
    the thinking section, control block, and signal block are invisible to callers.
    """
    model = _env("LLM_MODEL_TUTOR")
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
    call_id = str(uuid.uuid4())
    t0 = time.monotonic()

    response_format: dict = (
        {"type": "json_schema", "json_schema": {"name": "tutor_turn", "schema": schema, "strict": True}}
        if schema is not None
        else {"type": "json_object"}
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "response_format": response_format,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    url = f"{_base_url().rstrip('/')}/chat/completions"
    full_content = ""
    extractor = _ReplyExtractor()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code == 429:
                    body = await resp.aread()
                    yield ("error", f"OpenRouter rate-limited: {body[:200]}")
                    return
                if resp.status_code >= 400:
                    body = await resp.aread()
                    yield ("error", f"OpenRouter {resp.status_code}: {body[:200]}")
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    try:
                        delta = chunk_json["choices"][0]["delta"].get("content") or ""
                    except (KeyError, IndexError):
                        continue
                    if not delta:
                        continue
                    full_content += delta
                    tokens = extractor.feed(delta)
                    if tokens:
                        yield ("token", tokens)

    except Exception as exc:  # noqa: BLE001
        yield ("error", f"Stream error: {exc}")
        return

    if not full_content:
        yield ("error", "Empty response from model")
        return

    cleaned = _strip_fences(full_content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        yield ("error", f"Could not parse streaming response as JSON: {cleaned[:300]!r}")
        return

    _write_log({
        "event": "llm_call",
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "call_id": call_id,
        "session_id": session_id,
        "model": model,
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "input_tokens": 0,
        "output_tokens": len(full_content.split()),
        "raw_output": cleaned,
        "user_message_preview": next(
            (m["content"][:300] for m in reversed(messages) if m.get("role") == "user"), None
        ),
        "parse_success": None,
        "streamed": True,
    })
    yield ("state", parsed)
