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


def test_initial_understanding_captured_on_clarification_exit(client, fake_openrouter):
    """When the agent emits signal.refined_query, initial_understanding is set
    directly from that value (no LLM summariser)."""
    sid = _new_session(client, fake_openrouter)

    fake_openrouter.responses = [
        _agent_reply(
            "Great — let's break it down.",
            phase="decomposition",
            refined_query="I think we need to isolate x.",
        ),
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


def test_initial_understanding_not_overwritten(client, fake_openrouter):
    """Once initial_understanding is set from refined_query, later turns that
    also emit refined_query must not overwrite it."""
    sid = _new_session(client, fake_openrouter)

    # First turn sets initial_understanding via refined_query.
    fake_openrouter.responses = [
        _agent_reply(
            "Good — let's break it down.",
            phase="decomposition",
            refined_query="My first understanding.",
        ),
    ]
    client.post("/chat", json={"session_id": sid, "message": "My first understanding."})

    # Second turn also emits refined_query — must not overwrite.
    fake_openrouter.responses = [
        _agent_reply(
            "What's the first subproblem?",
            phase="decomposition",
            refined_query="A different framing.",
        ),
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


def test_wrap_up_complete_false_on_first_wrap_up_turn(client, fake_openrouter):
    """First turn entering wrap_up is always False — student must have a chance to respond."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply("Well done! You solved it.", phase="wrap_up"),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    assert resp.status_code == 200
    # First time entering wrap_up: student must still respond before session ends.
    assert resp.json()["wrap_up_complete"] is False


def test_wrap_up_complete_true_on_subsequent_wrap_up_turn(client, fake_openrouter):
    """wrap_up_complete is True once a wrap_up reflection has been answered AND graded.

    Walks the full three-turn dance: entry → reflection → quality. wrap_up_complete
    must stay False until the quality is recorded on the last turn.
    """
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: entering wrap_up. Agent doesn't emit reflection — the backend
    # will queue one deterministically on the next turn.
    fake_openrouter.responses = [
        _agent_reply("Walk me through it in your own words.", phase="wrap_up"),
    ]
    r1 = client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    assert r1.json()["wrap_up_complete"] is False

    # Turn 2: second wrap_up turn — backend queues a wrap_up reflection.
    # Session can't be complete yet — student needs to answer the reflection.
    fake_openrouter.responses = [
        _agent_reply("Anything else?"),
    ]
    r2 = client.post("/chat", json={"session_id": sid, "message": "I subtracted 3 then divided."})
    assert r2.json()["wrap_up_complete"] is False

    # Turn 3: student answers the reflection; agent evaluates quality + closes.
    fake_openrouter.responses = [
        _agent_reply("Nice reflection — see you next time!", last_reflection_quality="decent"),
    ]
    r3 = client.post("/chat", json={"session_id": sid, "message": "I learned to isolate x."})
    assert r3.status_code == 200
    assert r3.json()["wrap_up_complete"] is True


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


# ---------------------------------------------------------------------------
# Flow 4: backend-deterministic wrap_up reflection (Failure 2 fix)
# ---------------------------------------------------------------------------


def test_wrap_up_reflection_queued_deterministically(client, fake_openrouter):
    """On the SECOND wrap_up turn, when the agent emits empty signal, the backend
    must queue a wrap_up reflection itself. Mirrors the initial_understanding pattern."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1 (entering wrap_up): agent does not emit reflection.
    fake_openrouter.responses = [
        _agent_reply("Walk me through it in your own words.", phase="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    from app import session as session_mod
    session = session_mod.get(sid)
    # No reflection queued on the entry turn — student must answer synthesis first.
    assert not any(rp.trigger == "wrap_up" for rp in session.reflection_prompts)
    assert session.pending_reflection_index is None

    # Turn 2 (second wrap_up turn): agent still does not emit reflection.
    fake_openrouter.responses = [
        _agent_reply("Anything more?"),
    ]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I subtracted 3 then divided by 2."},
    )
    assert resp.status_code == 200

    session = session_mod.get(sid)
    # Backend must have queued a wrap_up reflection.
    wrap_up_rps = [rp for rp in session.reflection_prompts if rp.trigger == "wrap_up"]
    assert len(wrap_up_rps) == 1, "backend should have queued exactly one wrap_up reflection"
    assert session.pending_reflection_index is not None
    # The directive must be in the response so the frontend renders the card.
    directives = resp.json()["ui_directives"]
    assert any(d["component"] == "ReflectionPrompt" for d in directives), (
        f"ReflectionPrompt directive missing from response: {directives}"
    )
    # Reply must be suppressed (XOR with the reflection card).
    assert resp.json()["reply"] is None


def test_wrap_up_reflection_idempotent(client, fake_openrouter):
    """Once a wrap_up reflection exists in the session, subsequent turns must NOT
    queue another one."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: enter wrap_up. No reflection yet.
    fake_openrouter.responses = [
        _agent_reply("Walk me through it in your own words.", phase="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    # Turn 2: backend queues the reflection.
    fake_openrouter.responses = [_agent_reply("Anything more?")]
    client.post("/chat", json={"session_id": sid, "message": "I subtracted then divided."})

    # Turn 3: student answers reflection, agent records quality. Clears pending index.
    fake_openrouter.responses = [
        _agent_reply("Nice reflection.", last_reflection_quality="decent"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "I learned to isolate x."})

    # Turn 4: another wrap_up turn — backend must NOT queue a second reflection.
    fake_openrouter.responses = [_agent_reply("Take care.")]
    client.post("/chat", json={"session_id": sid, "message": "Thanks!"})

    from app import session as session_mod
    session = session_mod.get(sid)
    wrap_up_rps = [rp for rp in session.reflection_prompts if rp.trigger == "wrap_up"]
    assert len(wrap_up_rps) == 1, (
        f"backend queued a second wrap_up reflection (idempotency broken): "
        f"{[rp.question for rp in wrap_up_rps]}"
    )


def test_wrap_up_reflection_directive_without_agent_signal(client, fake_openrouter):
    """The ReflectionPrompt directive must appear even when the agent never emits
    signal.emit_reflection — the injection now keys off pending_reflection_index."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply("Walk me through it in your own words.", phase="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    fake_openrouter.responses = [_agent_reply("Anything more?")]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I subtracted 3 then divided by 2."},
    )

    body = resp.json()
    refl_directives = [d for d in body["ui_directives"] if d["component"] == "ReflectionPrompt"]
    assert len(refl_directives) == 1
    assert refl_directives[0]["props"]["trigger"] == "wrap_up"
    # Question must come from the wrap_up bank.
    from app.chat import REFLECTION_QUESTIONS
    assert refl_directives[0]["props"]["question"] in REFLECTION_QUESTIONS["wrap_up"]


def test_wrap_up_complete_blocked_until_quality_recorded(client, fake_openrouter):
    """wrap_up_complete must stay False until at least one wrap_up reflection has
    quality recorded, even if pending_reflection_index is None."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: entry. Reply contains synthesis cue so safety-net doesn't fire.
    fake_openrouter.responses = [
        _agent_reply("Walk me through it in your own words.", phase="wrap_up"),
    ]
    r1 = client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    assert r1.json()["wrap_up_complete"] is False

    # Turn 2: backend queues reflection. pending_reflection_index set → not complete.
    fake_openrouter.responses = [_agent_reply("Anything more?")]
    r2 = client.post(
        "/chat",
        json={"session_id": sid, "message": "I subtracted 3 then divided."},
    )
    assert r2.json()["wrap_up_complete"] is False


# ---------------------------------------------------------------------------
# Flow 5: synthesis safety-net (Failure 1 fix)
# ---------------------------------------------------------------------------


def test_synthesis_safety_net_fires_on_content_question(client, fake_openrouter):
    """When the agent transitions to wrap_up but asks a content question instead
    of the synthesis question (no closure phrases, no synthesis cues), the
    safety-net must append the synthesis question."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Agent transitions to wrap_up with a content-style question — no closure
    # phrase like "well done", no synthesis cue like "in your own words".
    fake_openrouter.responses = [
        _agent_reply(
            "Is there one of these that still feels a bit confusing?",
            phase="wrap_up",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    # The agent's content question must still be there.
    assert "Is there one of these" in reply
    # The synthesis ask must have been appended by the safety net.
    assert "walk me through" in reply.lower() or "your own words" in reply.lower()


def test_synthesis_safety_net_skips_when_synthesis_cue_present(client, fake_openrouter):
    """When the agent's reply already contains a synthesis cue, the safety-net
    must NOT append a second copy."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply(
            "Can you walk me through how you got there in your own words?",
            phase="wrap_up",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    reply = resp.json()["reply"]
    # Only one synthesis cue — the safety-net didn't duplicate.
    assert reply.lower().count("walk me through") == 1


# ---------------------------------------------------------------------------
# Flow 6: graceful close — strip trailing questions on the close turn so the
# WrapUpView transition doesn't cut the student off mid-question.
# ---------------------------------------------------------------------------


def _drive_to_close_turn(client, fake_openrouter, sid):
    """Helper: advance the session to the turn where the wrap_up reflection is
    pending. Caller then sends the close turn with last_reflection_quality."""
    _advance_to_wrap_up(client, fake_openrouter, sid)
    # Turn 1: entry into wrap_up.
    fake_openrouter.responses = [
        _agent_reply("Walk me through it in your own words.", phase="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})
    # Turn 2: backend queues wrap_up reflection.
    fake_openrouter.responses = [_agent_reply("Anything more?")]
    client.post("/chat", json={"session_id": sid, "message": "I subtracted then divided."})


def test_close_turn_strips_trailing_question(client, fake_openrouter):
    """When the agent emits last_reflection_quality but ALSO asks another question,
    the trailing question must be stripped so the WrapUpView transition is clean."""
    sid = _new_session(client, fake_openrouter)
    _drive_to_close_turn(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply(
            "I see what you mean. To be really specific, what are the three rules?",
            last_reflection_quality="shallow",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "I learned to isolate x."})
    assert resp.status_code == 200
    body = resp.json()
    # wrap_up_complete must be True now (quality recorded).
    assert body["wrap_up_complete"] is True
    # The trailing question must be gone.
    assert "?" not in body["reply"]
    # The leading declarative sentence is preserved.
    assert "I see what you mean." in body["reply"]


def test_close_turn_preserves_question_free_reply(client, fake_openrouter):
    """When the agent's close reply is already question-free, it passes through unchanged."""
    sid = _new_session(client, fake_openrouter)
    _drive_to_close_turn(client, fake_openrouter, sid)

    clean_close = "Nice reflection — that move from intuition to formal criteria will stick."
    fake_openrouter.responses = [
        _agent_reply(clean_close, last_reflection_quality="decent"),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "I learned to isolate x."})
    assert resp.json()["reply"] == clean_close
    assert resp.json()["wrap_up_complete"] is True


def test_close_turn_falls_back_when_reply_is_only_questions(client, fake_openrouter):
    """If the close reply is ENTIRELY questions, stripping yields empty — fall back
    to the canonical graceful-close phrase."""
    from app.chat import WRAP_UP_GRACEFUL_CLOSE

    sid = _new_session(client, fake_openrouter)
    _drive_to_close_turn(client, fake_openrouter, sid)

    fake_openrouter.responses = [
        _agent_reply(
            "What are the three rules? Can you list them now?",
            last_reflection_quality="shallow",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "I learned to isolate x."})
    assert resp.json()["reply"] == WRAP_UP_GRACEFUL_CLOSE
    assert resp.json()["wrap_up_complete"] is True


def test_close_turn_no_strip_outside_wrap_up(client, fake_openrouter):
    """last_reflection_quality emitted OUTSIDE wrap_up (e.g. periodic reflection in
    solving) must NOT strip questions — the agent may legitimately follow up."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)
    # Session is in solving after _advance_to_wrap_up — emit periodic reflection.
    fake_openrouter.responses = [
        _agent_reply(None, emit_reflection="periodic"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "Step 1 done."})

    # Student answers the periodic reflection; agent evaluates quality AND continues
    # with another question (legitimate mid-session pattern).
    fake_openrouter.responses = [
        _agent_reply(
            "Good catch. So what's the next step?",
            last_reflection_quality="decent",
        ),
    ]
    resp = client.post("/chat", json={"session_id": sid, "message": "I noticed I almost forgot."})
    # The follow-up question survives — we only strip in wrap_up.
    assert "?" in resp.json()["reply"]


# ---------------------------------------------------------------------------
# Flow 7: reflection "sticking like a mite" — idempotency + safety net
# ---------------------------------------------------------------------------
# In a real session the agent re-emitted signal.emit_reflection="wrap_up" on
# five consecutive turns; the backend queued a fresh ReflectionPrompt every
# time and rotated the question, so the student saw a different reflection card
# turn after turn. These four tests pin the fix:
#   A) idempotency guard in _apply_agent_response,
#   B) "already answered" guard in _build_chat_response,
#   C) forced-quality safety net firing at 2 turns,
#   D) safety net does NOT fire at 1 turn (agent gets one chance to evaluate).


def test_emit_reflection_idempotent_within_pending_window(client, fake_openrouter):
    """Re-emitting emit_reflection while a reflection is pending is dropped.

    Reproduces the live failure (session 3d77d42c…): agent emits
    emit_reflection="wrap_up" on multiple consecutive wrap_up turns. With
    Fix A, only the first emission queues a reflection; subsequent ones are
    ignored, the question bank is not rotated, and the user-facing directive
    is not re-injected.
    """
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: agent enters wrap_up + emits emit_reflection (queue 1st reflection).
    fake_openrouter.responses = [
        _agent_reply(None, phase="wrap_up", emit_reflection="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    from app import session as session_mod
    session = session_mod.get(sid)
    assert len(session.reflection_prompts) == 1
    assert session.pending_reflection_index == 0
    first_question = session.reflection_prompts[0].question

    # Turn 2: student answers; agent BOGUSLY re-emits emit_reflection.
    # Fix A must drop the new emission; the existing pending reflection stands.
    fake_openrouter.responses = [
        _agent_reply(None, emit_reflection="wrap_up"),
    ]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I solved it by subtracting 3 then dividing."},
    )

    session = session_mod.get(sid)
    # Still exactly one reflection; question hasn't rotated.
    assert len(session.reflection_prompts) == 1
    assert session.reflection_prompts[0].question == first_question
    # The pending index is unchanged.
    assert session.pending_reflection_index == 0
    # And the user does NOT see a fresh ReflectionPrompt card (Fix B —
    # response is set, so even with queued_rp the directive is suppressed).
    refl_directives = [
        d for d in resp.json()["ui_directives"]
        if d["component"] == "ReflectionPrompt"
    ]
    assert refl_directives == [], (
        f"reflection card re-injected after student already answered: {refl_directives}"
    )


def test_reflection_directive_not_reinjected_when_answered(client, fake_openrouter):
    """Fix B: when a queued reflection already has a student response and the
    agent emits a quiet turn, the backend must NOT inject the directive again."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: agent enters wrap_up + queues reflection.
    fake_openrouter.responses = [
        _agent_reply(None, phase="wrap_up", emit_reflection="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    # Turn 2: student answers reflection. Agent emits a quiet turn — no
    # emit_reflection, no last_reflection_quality, just a follow-up question
    # (the kind of behavior that drove the bug session into a loop).
    fake_openrouter.responses = [
        _agent_reply("Tell me more about that."),
    ]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I learned to isolate x."},
    )

    refl_directives = [
        d for d in resp.json()["ui_directives"]
        if d["component"] == "ReflectionPrompt"
    ]
    assert refl_directives == [], (
        f"reflection card injected on a turn where student had already responded: "
        f"{refl_directives}"
    )
    # And the agent's reply must NOT have been suppressed — there's no new
    # card replacing it, so the student must still see the follow-up text.
    assert resp.json()["reply"] == "Tell me more about that."


def test_force_quality_after_two_turns_without_eval(client, fake_openrouter):
    """Fix C: when the agent fails to emit last_reflection_quality after two
    finalized turns since the student responded, the backend force-attaches
    quality='decent' and lets wrap_up_complete flip True."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: enter wrap_up + queue reflection.
    fake_openrouter.responses = [
        _agent_reply(None, phase="wrap_up", emit_reflection="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    # Turn 2: student responds. Agent ignores its duty (no quality).
    # Counter -> 1, no force yet.
    fake_openrouter.responses = [_agent_reply("Mmhmm.")]
    r2 = client.post(
        "/chat",
        json={"session_id": sid, "message": "I learned to isolate x."},
    )
    assert r2.json()["wrap_up_complete"] is False

    # Turn 3: student responds again. Counter -> 2. Safety net fires.
    fake_openrouter.responses = [_agent_reply("Go on.")]
    r3 = client.post("/chat", json={"session_id": sid, "message": "nothing"})

    from app import session as session_mod
    from app.chat import WRAP_UP_GRACEFUL_CLOSE
    session = session_mod.get(sid)
    # Pending index cleared by force.
    assert session.pending_reflection_index is None
    # Quality force-attached to the original reflection.
    rp = session.reflection_prompts[0]
    assert rp.quality == "decent"
    # And wrap_up_complete is now True so the frontend can transition.
    assert r3.json()["wrap_up_complete"] is True
    # The agent's "Go on." dangling reply gets replaced with the canonical
    # graceful close so the auto-transition to WrapUpView doesn't cut a stale
    # message mid-screen.
    assert r3.json()["reply"] == WRAP_UP_GRACEFUL_CLOSE


def test_force_quality_does_not_fire_on_first_unevaluated_turn(client, fake_openrouter):
    """Safety net must NOT fire on the immediate turn after the student
    response — the agent gets one chance to emit last_reflection_quality
    before the backend gives up."""
    sid = _new_session(client, fake_openrouter)
    _advance_to_wrap_up(client, fake_openrouter, sid)

    # Turn 1: enter wrap_up + queue reflection.
    fake_openrouter.responses = [
        _agent_reply(None, phase="wrap_up", emit_reflection="wrap_up"),
    ]
    client.post("/chat", json={"session_id": sid, "message": "x is 2."})

    # Turn 2: student responds. Agent ignores its duty (no quality, no signal).
    # Counter goes 0 -> 1. Force threshold is 2, so no force yet.
    fake_openrouter.responses = [_agent_reply("Mmhmm.")]
    resp = client.post(
        "/chat",
        json={"session_id": sid, "message": "I learned to isolate x."},
    )

    from app import session as session_mod
    session = session_mod.get(sid)
    # Quality must still be None — the agent gets another shot next turn.
    assert session.reflection_prompts[0].quality is None
    assert session.pending_reflection_index == 0
    assert resp.json()["wrap_up_complete"] is False
    assert resp.json()["wrap_up_complete"] is False
