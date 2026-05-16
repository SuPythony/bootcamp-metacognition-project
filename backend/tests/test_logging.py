"""Tests for JSONL logging in llm.py and chat.py."""
from __future__ import annotations

import json
import pytest

# ---------------------------------------------------------------------------
# L1.1 — call_classifier emits llm_classifier log event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_writes_log(fake_openrouter, loaded_registry, monkeypatch):
    logged = []
    from app import llm as llm_mod

    monkeypatch.setattr(llm_mod, "_write_log", lambda entry: logged.append(entry))
    fake_openrouter.responses = ['{"domain": "math", "complexity_hint": "multi-step"}']

    from app.llm import call_classifier

    result, _usage = await call_classifier("solve 2x + 3 = 7", session_id="sess-test")

    classifier_events = [e for e in logged if e.get("event") == "llm_classifier"]
    assert len(classifier_events) == 1, f"Expected 1 llm_classifier event, got: {logged}"
    ev = classifier_events[0]
    assert ev["query"] == "solve 2x + 3 = 7"
    assert ev["result"]["domain"] == "math"
    assert ev["model"] == "test/classifier-model"
    assert ev["session_id"] == "sess-test"
    assert "latency_ms" in ev


# ---------------------------------------------------------------------------
# L1.3 — call_tutor emits user_message_preview in llm_call event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tutor_writes_user_preview(fake_openrouter, monkeypatch):
    logged = []
    from app import llm as llm_mod

    monkeypatch.setattr(llm_mod, "_write_log", lambda entry: logged.append(entry))
    monkeypatch.setenv("LLM_MODEL_TUTOR", "test/tutor-model")

    reply = {
        "thinking": "scratch",
        "reply": "What do you know about this already?",
        "control": {
            "phase": "clarification",
            "active_subproblem": None,
            "hint_level": None,
            "tool_call": None,
            "ui_directives": [],
        },
        "signal": {},
    }
    fake_openrouter.responses = [json.dumps(reply)]

    from app.llm import call_tutor

    messages = [
        {"role": "system", "content": "You are a tutor."},
        {"role": "user", "content": "I need help with quadratic equations"},
    ]
    _raw, _usage = await call_tutor(messages, session_id="sess-preview")

    llm_call_events = [e for e in logged if e.get("event") == "llm_call"]
    assert len(llm_call_events) >= 1, f"Expected llm_call events, got: {[e['event'] for e in logged]}"
    ev = llm_call_events[0]
    assert "user_message_preview" in ev
    assert "quadratic equations" in (ev["user_message_preview"] or "")


# ---------------------------------------------------------------------------
# L1.4 — POST /chat emits chat_turn event to chat.jsonl logger
# ---------------------------------------------------------------------------


def test_chat_turn_writes_chat_log(fake_openrouter, loaded_registry, tmp_persona_dir, monkeypatch):
    chat_logged = []
    from app import chat as chat_mod

    monkeypatch.setattr(chat_mod, "_write_chat_log", lambda entry: chat_logged.append(entry))
    from app import llm as llm_mod
    monkeypatch.setattr(llm_mod, "_write_log", lambda entry: None)

    from app import session as session_mod
    from app.session import Session

    sess = Session(
        session_id="test-sess-log",
        username="testuser",
        mode="solving",
        domain="math",
        original_query="solve x+1=5",
    )
    session_mod.put(sess)

    reply = {
        "thinking": "",
        "reply": "What is your current thinking on this?",
        "control": {
            "phase": "clarification",
            "active_subproblem": None,
            "hint_level": None,
            "tool_call": None,
            "ui_directives": [],
        },
        "signal": {},
    }
    fake_openrouter.responses = [json.dumps(reply)]

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/chat",
            json={"session_id": "test-sess-log", "message": "I have no idea"},
        )
    assert resp.status_code == 200, resp.text

    turn_events = [e for e in chat_logged if e.get("event") == "chat_turn"]
    assert len(turn_events) == 1, f"Expected 1 chat_turn event, got: {chat_logged}"
    ev = turn_events[0]
    assert ev["session_id"] == "test-sess-log"
    assert ev["phase"] == "clarification"
    assert ev["user_message"] == "I have no idea"
