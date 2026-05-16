"""Tests for clarification initial_understanding capture, calibration/reflection XOR,
wrap_up_complete signal, and reflection question de-duplication.

All tests use the fake_openrouter fixture — no real LLM calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

_SIGNAL_FIELDS = frozenset({
    "subproblem_updates", "emit_reflection", "last_reflection_quality",
    "emit_calibration_check", "calibration_outcome", "persona_updates",
    "self_correction_noted", "escape_hatch_triggered", "escape_hatch_reflection",
    "verification_prompted", "concepts_established", "student_question_quality",
    "decomposition_source", "disengagement_noted", "refined_query",
})


def _agent_reply(reply: str | None = None, **overrides) -> str:
    control = {k: v for k, v in overrides.items() if k not in _SIGNAL_FIELDS}
    signal_data = {k: v for k, v in overrides.items() if k in _SIGNAL_FIELDS}
    payload: dict = {"reply": reply, "control": control}
    if signal_data:
        payload["signal"] = signal_data
    return json.dumps(payload)


def _classifier_reply(domain: str = "math") -> str:
    return json.dumps({"domain": domain, "complexity_hint": "single-step"})


@pytest.fixture
def client(fake_openrouter, loaded_registry, tmp_persona_dir):
    from app.main import app
    with TestClient(app) as c:
        yield c


def _new_session(client, fake_openrouter, opening_reply="What's your current thinking?"):
    """Create a session in clarification phase. Returns session_id."""
    fake_openrouter.responses = [
        _classifier_reply(),
        _agent_reply(opening_reply),
    ]
    resp = client.post(
        "/session/new",
        json={"username": "testuser", "mode": "solving", "query": "solve 2x+3=7"},
    )
    assert resp.status_code == 200
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Flow 1: initial_understanding capture
# ---------------------------------------------------------------------------


def test_initial_understanding_captured_on_clarification_exit(client, fake_openrouter, monkeypatch):
    """When the agent transitions from clarification to decomposition,
    initial_understanding is populated via the LLM summariser."""
    from app import llm as llm_mod
    monkeypatch.setattr(
        llm_mod, "call_initial_understanding_summarizer",
        AsyncMock(return_value="I think we need to isolate x."),
    )
    sid = _new_session(client, fake_openrouter)

    fake_openrouter.responses = [
        _agent_reply("Great — let's break it down.", phase="decomposition"),
    ]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I think we need to isolate x."},
    )
    assert resp.status_code == 200

    from app import session as session_mod
    session = session_mod.get(sid)
    assert session is not None
    assert session.initial_understanding == "I think we need to isolate x."


def test_initial_understanding_not_overwritten(client, fake_openrouter, monkeypatch):
    """Once initial_understanding is set, subsequent turns must not overwrite it."""
    from app import llm as llm_mod
    monkeypatch.setattr(
        llm_mod, "call_initial_understanding_summarizer",
        AsyncMock(return_value="My first understanding."),
    )
    sid = _new_session(client, fake_openrouter)

    fake_openrouter.responses = [
        _agent_reply("Good — let's break it down.", phase="decomposition"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "My first understanding."})

    # Another turn in decomposition — summariser must not be called again.
    fake_openrouter.responses = [
        _agent_reply("What's the first subproblem?", phase="decomposition"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "A second message."})

    from app import session as session_mod
    session = session_mod.get(sid)
    assert session.initial_understanding == "My first understanding."


def test_initial_understanding_not_set_while_still_clarifying(client, fake_openrouter):
    """A clarification→clarification turn must not call the summariser."""
    sid = _new_session(client, fake_openrouter)

    # Agent stays in clarification (no phase field = None = stay).
    fake_openrouter.responses = [
        _agent_reply("Can you say more about what you already know?"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "I have no idea."})

    from app import session as session_mod
    session = session_mod.get(sid)
    assert session.initial_understanding is None


# ---------------------------------------------------------------------------
# Flow 2: Calibration XOR — reply suppressed when emit_calibration_check
# ---------------------------------------------------------------------------


def test_calibration_check_suppresses_reply(client, fake_openrouter):
    """When emit_calibration_check is True, reply must be None in the response."""
    sid = _new_session(client, fake_openrouter)

    fake_openrouter.responses = [
        _agent_reply(
            "Before you try — how confident are you?",
            emit_calibration_check=True,
        ),
    ]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I think I understand it."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] is None
    # Widget directive still present.
    assert any(d["component"] == "CalibrationCheck" for d in body["ui_directives"])


def test_calibration_check_with_no_reply_still_works(client, fake_openrouter):
    """emit_calibration_check with reply=None (model already null) is fine."""
    sid = _new_session(client, fake_openrouter)

    fake_openrouter.responses = [
        _agent_reply(None, emit_calibration_check=True),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "Sure."})
    assert resp.status_code == 200
    assert resp.json()["reply"] is None
    assert any(d["component"] == "CalibrationCheck" for d in resp.json()["ui_directives"])


# ---------------------------------------------------------------------------
# Flow 2: Calibration XOR — reply suppressed when emit_reflection
# ---------------------------------------------------------------------------


def test_reflection_xor_suppresses_reply(client, fake_openrouter):
    """When emit_reflection is set, reply must be None in the response."""
    sid = _new_session(client, fake_openrouter)

    # Advance to decomposition first so wrap_up is reachable.
    fake_openrouter.responses = [
        _agent_reply("Let's break it down.", phase="decomposition"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "I think we isolate x."})

    # Advance to solving.
    fake_openrouter.responses = [
        _agent_reply("Okay, what's your first step?", phase="solving"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "Subtract 3 from both sides."})

    # Agent emits wrap_up + emit_reflection.
    fake_openrouter.responses = [
        _agent_reply(
            "Can you walk me through the whole solution?",
            phase="wrap_up",
            emit_reflection="wrap_up",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "x equals 2."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] is None
    assert any(d["component"] == "ReflectionPrompt" for d in body["ui_directives"])


# ---------------------------------------------------------------------------
# Flow 3: wrap_up_complete — correct values across the reflection lifecycle
# ---------------------------------------------------------------------------


def _advance_to_wrap_up(client, fake_openrouter, sid):
    """Helper: advance session through decomposition → solving → wrap_up."""
    fake_openrouter.responses = [
        _agent_reply("Break it down.", phase="decomposition"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "I understand now."})

    fake_openrouter.responses = [
        _agent_reply("Let's solve it.", phase="solving"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "Subtract 3."})


def test_wrap_up_complete_false_while_reflection_pending(client, fake_openrouter):
    """wrap_up_complete must be False on the turn that emits emit_reflection."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply(
            "Can you walk me through it?",
            phase="wrap_up",
            emit_reflection="wrap_up",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "x equals 2."})
    assert resp.status_code == 200
    assert resp.json()["wrap_up_complete"] is False


def test_wrap_up_complete_true_after_quality_evaluation(client, fake_openrouter):
    """wrap_up_complete must be True on the turn last_reflection_quality arrives."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: agent emits wrap_up + emit_reflection.
    fake_openrouter.responses = [
        _agent_reply(None, phase="wrap_up", emit_reflection="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    # Turn 2: student writes their reflection (plain message).
    fake_openrouter.responses = [
        _agent_reply("Nice reflection!", last_reflection_quality="decent"),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "I learned to isolate x."})
    assert resp.status_code == 200
    assert resp.json()["wrap_up_complete"] is True


def test_wrap_up_complete_true_without_reflection(client, fake_openrouter):
    """If agent enters wrap_up without emitting emit_reflection, wrap_up_complete
    is True immediately (no reflection pending)."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply("Well done! You solved it.", phase="wrap_up"),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    assert resp.status_code == 200
    # No pending reflection → immediately complete.
    assert resp.json()["wrap_up_complete"] is True


# ---------------------------------------------------------------------------
# Flow 3: Reflection question de-duplication
# ---------------------------------------------------------------------------


def test_reflection_question_not_repeated_in_session(client, fake_openrouter):
    """The second reflection in a session must use a different question than the first."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # First reflection: periodic.
    fake_openrouter.responses = [
        _agent_reply(None, phase="wrap_up", emit_reflection="periodic"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    # Student responds.
    fake_openrouter.responses = [
        _agent_reply("Good.", last_reflection_quality="decent"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "It was similar to last time."})

    # Second reflection: periodic again.
    fake_openrouter.responses = [
        _agent_reply(None, emit_reflection="periodic"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "Now what?"})

    from app import session as session_mod
    session = session_mod.get(sid)
    assert len(session.reflection_prompts) >= 2
    q1 = session.reflection_prompts[0].question
    q2 = session.reflection_prompts[1].question
    # Different questions selected (de-duplication).
    assert q1 != q2, f"Same question used twice: {q1!r}"


def test_reflection_dedup_falls_back_when_bank_exhausted(client, fake_openrouter):
    """If all questions in the bank have been asked, selection falls back to the
    full bank (no crash, no infinite loop)."""
    from app.chat import REFLECTION_QUESTIONS

    bank = REFLECTION_QUESTIONS["periodic"]
    sid = _new_session(client, fake_openrouter)

    # Manually inject all periodic questions into the session's reflection_prompts.
    from app import session as session_mod
    from app.session import ReflectionPrompt

    session = session_mod.get(sid)
    for q in bank:
        session.reflection_prompts.append(
            ReflectionPrompt(trigger="periodic", question=q, response="ok", quality="decent")
        )
    session_mod.put(session)

    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Trigger another periodic reflection — should not crash.
    fake_openrouter.responses = [
        _agent_reply(None, emit_reflection="periodic"),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "Another turn."})
    assert resp.status_code == 200
    # A question was selected (any from the bank is fine).
    session = session_mod.get(sid)
    last_q = session.reflection_prompts[-1].question
    assert last_q in bank
