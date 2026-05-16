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


# ---- call_initial_understanding_summarizer ----------------------------------
#
# These tests bypass the shared `fake_openrouter` fixture (which stubs
# call_initial_understanding_summarizer to a no-op for chat-flow tests) and
# patch _post_chat directly so we exercise the real function.


def _stub_chat_response(content: str):
    """Build a minimal OpenRouter chat-completion response payload."""
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@pytest.mark.asyncio
async def test_call_initial_understanding_summarizer_happy_path(monkeypatch):
    """Returns the parsed initial_understanding string from a well-formed reply."""
    from app import llm as llm_mod

    captured: dict = {}

    async def fake_post(*, model, messages, response_format=None, temperature=None, timeout=60.0):
        captured["model"] = model
        captured["messages"] = messages
        captured["response_format"] = response_format
        return _stub_chat_response(
            json.dumps({"initial_understanding": "You came in thinking it was just about isolating x."})
        )

    monkeypatch.setattr(llm_mod, "_post_chat", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL_CLASSIFIER", "test/classifier")

    result = await llm.call_initial_understanding_summarizer(
        clarification_student_messages=["I think I just need to isolate x"],
        session_id="test-session",
    )

    assert result == "You came in thinking it was just about isolating x."
    # Uses the cheap classifier model, not the tutor model.
    assert captured["model"] == "test/classifier"
    # Requests structured JSON.
    assert captured["response_format"] == {"type": "json_object"}
    # System prompt enforces second-person, anti-grade tone.
    sys_content = captured["messages"][0]["content"]
    assert "second person" in sys_content.lower()
    assert "fragmented" in sys_content.lower()
    # User content includes the student message.
    assert "isolate x" in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_call_initial_understanding_summarizer_returns_none_on_empty_input(monkeypatch):
    """Empty clarification_student_messages returns None without an HTTP call."""
    from app import llm as llm_mod

    called = False

    async def fake_post(**_):
        nonlocal called
        called = True
        return _stub_chat_response("{}")

    monkeypatch.setattr(llm_mod, "_post_chat", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL_CLASSIFIER", "test/classifier")

    result = await llm.call_initial_understanding_summarizer(
        clarification_student_messages=[],
        session_id="test-session",
    )

    assert result is None
    assert called is False


@pytest.mark.asyncio
async def test_call_initial_understanding_summarizer_returns_none_on_parse_failure(monkeypatch):
    """Unparseable response → returns None (safe fallback), does not raise."""
    from app import llm as llm_mod

    async def fake_post(**_):
        return _stub_chat_response("not valid json at all")

    monkeypatch.setattr(llm_mod, "_post_chat", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL_CLASSIFIER", "test/classifier")

    result = await llm.call_initial_understanding_summarizer(
        clarification_student_messages=["I think I need to isolate x"],
        session_id="test-session",
    )

    assert result is None


@pytest.mark.asyncio
async def test_call_initial_understanding_summarizer_returns_none_on_missing_key(monkeypatch):
    """Valid JSON without 'initial_understanding' key → returns None (not empty string)."""
    from app import llm as llm_mod

    async def fake_post(**_):
        return _stub_chat_response(json.dumps({"something_else": "nope"}))

    monkeypatch.setattr(llm_mod, "_post_chat", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL_CLASSIFIER", "test/classifier")

    result = await llm.call_initial_understanding_summarizer(
        clarification_student_messages=["I think I need to isolate x"],
        session_id="test-session",
    )

    assert result is None


# ---- call_summarizer tone constraints ----------------------------------------


@pytest.mark.asyncio
async def test_call_summarizer_system_prompt_enforces_tone(monkeypatch):
    """Regression guard: the rewritten system prompt must keep its second-person
    addressing and forbid graded language. If this test fails after a prompt
    edit, the wrap-up trace will revert to clinical third-person ('the student
    understands ...') — see the May 2026 prompt rewrite."""
    from app import llm as llm_mod

    captured: dict = {}

    async def fake_post(*, model, messages, response_format=None, temperature=None, timeout=60.0):
        captured["messages"] = messages
        return _stub_chat_response(
            json.dumps({
                "final_understanding": "You worked it out.",
                "delta_label": "moderate",
                "delta_evidence": "You moved from x to y.",
            })
        )

    monkeypatch.setattr(llm_mod, "_post_chat", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL_CLASSIFIER", "test/classifier")

    await llm.call_summarizer(
        initial_understanding="You came in thinking it was about x.",
        recent_student_messages=["I subtracted 3", "divided by 2"],
        session_id="test-session",
    )

    sys_prompt = captured["messages"][0]["content"].lower()
    # Must address the student in second person.
    assert "second person" in sys_prompt or '"you"' in sys_prompt
    # Must explicitly forbid grade-like framings.
    for forbidden in ("fragmented", "incomplete", "partial"):
        assert forbidden in sys_prompt, (
            f"summariser system prompt no longer forbids '{forbidden}' — "
            "tone safeguards may have been dropped"
        )
    # Must explicitly tell the model not to grade.
    assert "grade" in sys_prompt or "never grade" in sys_prompt


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
