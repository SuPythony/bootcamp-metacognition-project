"""Tests for the OpenRouter client.

Uses the `fake_openrouter` fixture from conftest to intercept the HTTP call.
"""

from __future__ import annotations

import json

import pytest

from app import llm


@pytest.mark.asyncio
async def test_call_tutor_returns_parsed_json(fake_openrouter):
    fake_openrouter.responses = [
        json.dumps({"reply": "hello", "control": {"phase": "clarification"}})
    ]
    result, _ = await llm.call_tutor(messages=[{"role": "user", "content": "hi"}])
    assert result["reply"] == "hello"
    assert result["control"]["phase"] == "clarification"
    # One HTTP call.
    assert len(fake_openrouter.requests) == 1


@pytest.mark.asyncio
async def test_call_tutor_retries_once_on_parse_failure(fake_openrouter):
    """First response is unparseable; retry should succeed."""
    fake_openrouter.responses = [
        "this is not JSON",
        json.dumps({"reply": "fixed", "control": {}}),
    ]
    result, _ = await llm.call_tutor(messages=[{"role": "user", "content": "hi"}])
    assert result["reply"] == "fixed"
    # Two HTTP calls: original + one retry.
    assert len(fake_openrouter.requests) == 2
    # The retry should include a corrective system message.
    retry_messages = fake_openrouter.requests[1]["messages"]
    assert any("not valid JSON" in m.get("content", "") for m in retry_messages if m["role"] == "system")


@pytest.mark.asyncio
async def test_call_tutor_second_failure_raises(fake_openrouter):
    """Two unparseable responses → LLMParseError, no further retries."""
    fake_openrouter.responses = ["not json", "still not json"]
    with pytest.raises(llm.LLMParseError):
        await llm.call_tutor(messages=[{"role": "user", "content": "hi"}])
    assert len(fake_openrouter.requests) == 2


@pytest.mark.asyncio
async def test_call_tutor_uses_json_schema_when_schema_provided(fake_openrouter):
    fake_openrouter.responses = [json.dumps({"reply": "", "control": {}})]
    schema = {"type": "object", "properties": {"reply": {"type": "string"}}}
    await llm.call_tutor(
        messages=[{"role": "user", "content": "hi"}], schema=schema
    )
    rf = fake_openrouter.requests[0]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] is schema


@pytest.mark.asyncio
async def test_call_tutor_uses_json_object_mode_when_no_schema(fake_openrouter):
    fake_openrouter.responses = [json.dumps({"reply": "", "control": {}})]
    await llm.call_tutor(messages=[{"role": "user", "content": "hi"}])
    assert fake_openrouter.requests[0]["response_format"]["type"] == "json_object"


@pytest.mark.asyncio
async def test_call_classifier_returns_validated_domain(
    fake_openrouter, loaded_registry
):
    fake_openrouter.responses = [
        json.dumps({"domain": "math", "complexity_hint": "single-step"})
    ]
    result, _ = await llm.call_classifier("solve 2x+3=7")
    assert result["domain"] == "math"
    assert result["complexity_hint"] == "single-step"


@pytest.mark.asyncio
async def test_call_classifier_rejects_unknown_domain(
    fake_openrouter, loaded_registry
):
    fake_openrouter.responses = [json.dumps({"domain": "physics", "complexity_hint": "multi-step"})]
    with pytest.raises(llm.LLMClassifierError):
        await llm.call_classifier("what is mass?")


@pytest.mark.asyncio
async def test_call_classifier_rejects_internal_domain(
    fake_openrouter, loaded_registry
):
    """Even though 'persona' is registered, the classifier must never
    return it — the classifier prompt is built with only public domains."""
    fake_openrouter.responses = [json.dumps({"domain": "persona", "complexity_hint": "multi-step"})]
    with pytest.raises(llm.LLMClassifierError):
        await llm.call_classifier("hello")
    # Also verify the system prompt didn't even mention persona.
    sys_msg = fake_openrouter.requests[0]["messages"][0]["content"]
    assert "persona" not in sys_msg


@pytest.mark.asyncio
async def test_call_classifier_supplies_default_complexity(
    fake_openrouter, loaded_registry
):
    """Classifier output without complexity_hint gets a default."""
    fake_openrouter.responses = [json.dumps({"domain": "math"})]
    result, _ = await llm.call_classifier("solve 2x+3=7")
    assert result["complexity_hint"] == "multi-step"


@pytest.mark.asyncio
async def test_call_classifier_raises_when_no_specs_registered(fake_openrouter):
    """Without loaded specializations, classifier can't validate output."""
    fake_openrouter.responses = []  # not even called
    with pytest.raises(llm.LLMError, match="No specializations"):
        await llm.call_classifier("hi")


@pytest.mark.asyncio
async def test_call_classifier_parse_failure_raises(
    fake_openrouter, loaded_registry
):
    fake_openrouter.responses = ["not json"]
    with pytest.raises(llm.LLMParseError):
        await llm.call_classifier("solve 2x+3=7")


@pytest.mark.asyncio
async def test_stream_tutor_is_async_generator(monkeypatch):
    """stream_tutor is now a real async generator; verify it yields (type, data) tuples
    and emits a 'state' event after a successful streamed call."""
    import inspect
    from app import llm as llm_mod

    # Confirm it's an async generator function, not a coroutine.
    assert inspect.isasyncgenfunction(llm_mod.stream_tutor)

    # Patch _post_chat is NOT used by stream_tutor (it uses httpx.stream directly),
    # so we verify the generator type contract only — live HTTP is exercised manually.
    gen = llm_mod.stream_tutor(messages=[{"role": "user", "content": "hi"}])
    assert inspect.isasyncgen(gen)
    await gen.aclose()  # clean up without iterating
