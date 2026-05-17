"""Integration tests for the /session/new + /chat pipeline.

Uses FastAPI's TestClient and the fake_openrouter fixture from conftest to
intercept LLM calls. No real OpenRouter traffic — every test queues the
exact response shape the agent would emit.
"""

from __future__ import annotations

import json
import sys
import types

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
    """Build a single JSON-encoded agent response.

    Keyword args matching _SIGNAL_FIELDS are routed to the `signal` block;
    all others go into `control`. Omits signal entirely when no signal kwargs
    are provided (matches new schema semantics).
    """
    control = {k: v for k, v in overrides.items() if k not in _SIGNAL_FIELDS}
    signal_data = {k: v for k, v in overrides.items() if k in _SIGNAL_FIELDS}
    payload: dict = {"reply": reply, "control": control}
    if signal_data:
        payload["signal"] = signal_data
    return json.dumps(payload)


def _classifier_reply(domain: str, complexity: str = "single-step") -> str:
    return json.dumps({"domain": domain, "complexity_hint": complexity})


@pytest.fixture
def client(fake_openrouter, loaded_registry, tmp_persona_dir):
    """TestClient wired with mocked LLM, loaded specializations, and an
    isolated persona directory."""
    from app.main import app

    with TestClient(app) as c:
        yield c


# ---- /session/new -----------------------------------------------------------


def test_session_new_happy_path(client, fake_openrouter):
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your current thinking on this?"),
    ]
    resp = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "solve 2x+3=7"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "solving"
    assert body["domain"] == "math"
    assert "session_id" in body
    assert "What's your current thinking" in body["opening_message"]


def test_session_new_rejects_critique_mode(client, fake_openrouter):
    resp = client.post(
        "/session/new",
        json={"username": "alice", "mode": "critique", "query": "..."},
    )
    assert resp.status_code in (400, 422)


def test_session_new_rejects_unknown_mode(client, fake_openrouter):
    resp = client.post(
        "/session/new",
        json={"username": "alice", "mode": "freeform", "query": "..."},
    )
    assert resp.status_code in (400, 422)


def test_session_new_classifier_rejected_for_internal_domain(client, fake_openrouter):
    """If the classifier somehow returns persona, the API must 502 — never
    create a user session against a reserved internal domain."""
    fake_openrouter.responses = [_classifier_reply("persona")]
    resp = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "..."},
    )
    # call_classifier itself rejects 'persona' as not in the public domain
    # list, raising LLMClassifierError before we ever get to the is_internal
    # check. Either way, request fails.
    assert resp.status_code in (500, 502)


# ---- /chat ------------------------------------------------------------------


def test_chat_404_unknown_session(client):
    resp = client.post("/chat", json={"session_id": "nope", "message": "hi"})
    assert resp.status_code == 404


def test_chat_requires_exactly_one_input(client, fake_openrouter):
    fake_openrouter.responses = [_classifier_reply("math"), _agent_reply("clar?")]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()

    # No input at all
    resp = client.post("/chat", json={"session_id": new["session_id"]})
    assert resp.status_code == 400

    # Two inputs at once
    resp = client.post(
        "/chat",
        json={
            "session_id": new["session_id"],
            "message": "hi",
            "directive_response": {"component": "x", "value": 1},
        },
    )
    assert resp.status_code == 400


def test_chat_happy_path_phase_transition(client, fake_openrouter):
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),  # opening turn (clarification)
        _agent_reply(
            "Got it. What's the first piece you'd tackle?",
            phase="decomposition",
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat",
        json={"session_id": new["session_id"], "message": "I need to isolate x"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["phase"] == "decomposition"
    assert "first piece" in body["reply"]


def test_chat_clamps_illegal_phase_jump(client, fake_openrouter):
    """Illegal phase jump (clarification → wrap_up) is clamped to current phase,
    not rejected. See CLAUDE.md: "clamped to current phase with a warning log"."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply("Skipping to the end!", phase="wrap_up"),  # illegal from clarification
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "I dunno"}
    )
    assert resp.status_code == 200
    # Phase is clamped back to clarification (illegal transition blocked).
    assert resp.json()["phase"] == "clarification"


def test_chat_clamps_hint_level_jump(client, fake_openrouter):
    """Agent emits hint_level=5 starting from 0 — must be clamped to 1."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Got it. What's the first piece?",
            phase="decomposition",
        ),
        _agent_reply(
            "Let's start with this part.",
            phase="solving",
            subproblem_updates=[
                {"id": "sp-1", "description": "isolate x", "status": "active"}
            ],
            active_subproblem="sp-1",
        ),
        # Now agent jumps to hint_level 5 from 0 — should clamp.
        _agent_reply("Big hint!", hint_level=5),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "I think I get it"})
    client.post("/chat", json={"session_id": sid, "message": "Looks good"})
    resp = client.post("/chat", json={"session_id": sid, "message": "I'm stuck"})
    assert resp.status_code == 200
    # Inspect the session state to verify clamping.
    from app import session as session_mod

    s = session_mod.get(sid)
    sp = next(sp for sp in s.subproblems if sp.id == "sp-1")
    assert sp.hints_given == 1  # clamped from 5 to 1 (current 0 + 1)


def test_chat_backend_tool_dispatch_round_trip(
    client, fake_openrouter, monkeypatch
):
    """Agent emits a backend tool_call → backend dispatches → result replayed
    into the agent → final reply produced. Only one /chat call from the
    client; the tool loop is internal."""
    # Inject a fake algebra tool module.
    fake = types.ModuleType("specializations.math.tools.algebra")

    def fake_run(args, session):
        return {"result": "x = 1", "display_data": {"steps": [], "final": "x = 1"}}

    fake.run = fake_run
    monkeypatch.setitem(sys.modules, "specializations.math.tools.algebra", fake)

    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Let me look that up.",
            tool_call={"name": "algebra", "args": {"expression": "x+1=2", "operation": "solve"}},
        ),
        _agent_reply("What does that result tell you?"),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "I think I get it"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # The final reply (after tool round-trip) is what the client sees.
    assert "What does that result tell you?" in body["reply"]
    # tool_calls list carries the backend tool result.
    assert len(body["tool_calls"]) > 0
    assert body["tool_calls"][0]["name"] == "algebra"


def test_chat_frontend_tool_surfaces_to_client(client, fake_openrouter):
    """Agent emits a frontend tool_call (programming.code_runner) → response
    carries frontend_tool_call; the call DOESN'T execute on the backend."""
    fake_openrouter.responses = [
        _classifier_reply("programming"),
        _agent_reply("How would you start?"),
        _agent_reply(
            "Let's run that snippet.",
            tool_call={"name": "code_runner", "args": {"code": "print(1)"}},
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "print hello"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "Like this?"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["frontend_tool_call"] is not None
    assert body["frontend_tool_call"]["name"] == "code_runner"
    assert body["frontend_tool_call"]["frontend_handler"] == "PyodideRunner"
    assert body["tool_calls"] == []


def test_chat_accepts_tool_result_after_frontend_call(client, fake_openrouter):
    """After a frontend_tool_call goes out, the next /chat sends tool_result
    and the agent produces a follow-up reply."""
    fake_openrouter.responses = [
        _classifier_reply("programming"),
        _agent_reply("How would you start?"),
        _agent_reply(
            "Let's run that.",
            tool_call={"name": "code_runner", "args": {"code": "print(1)"}},
        ),
        _agent_reply("What did the output tell you?"),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "print hello"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "Like this?"})
    resp = client.post(
        "/chat",
        json={
            "session_id": sid,
            "tool_result": {
                "name": "code_runner",
                "result": "1\n",
                "display_data": {"stdout": "1\n", "stderr": "", "exit_code": 0},
            },
        },
    )
    assert resp.status_code == 200
    assert "What did the output tell you" in resp.json()["reply"]


def test_chat_rejects_tool_result_without_pending_call(client, fake_openrouter):
    """tool_result with no pending frontend tool is a client bug."""
    fake_openrouter.responses = [_classifier_reply("math"), _agent_reply("clar?")]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat",
        json={
            "session_id": new["session_id"],
            "tool_result": {"name": "code_runner", "result": "1"},
        },
    )
    assert resp.status_code == 400


# ---- Persona onboarding -----------------------------------------------------


def test_persona_create_pending_when_no_file(client, fake_openrouter, tmp_persona_dir):
    fake_openrouter.responses = [_agent_reply("What's your age or school year?")]
    resp = client.post("/persona/create", json={"username": "alice", "confirm": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["session_id"] is not None
    assert body["opening_message"] is not None


def test_persona_create_exists_when_file_present(client, tmp_persona_dir):
    from app import persona as persona_mod
    from app.session import Persona

    persona_mod.save_persona(
        Persona(
            username="alice",
            created_at="2026-05-14T00:00:00Z",
            age_band="13-15",
            school_level="lower_secondary",
            initial_intent="ace my math test",
        )
    )
    resp = client.post("/persona/create", json={"username": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "exists"
    assert body["persona"]["age_band"] == "13-15"


def test_persona_full_onboarding_writes_stub(client, fake_openrouter, tmp_persona_dir):
    """End-to-end: create pending session → two /chat turns → persona file
    lands on disk."""
    fake_openrouter.responses = [
        _agent_reply("What's your age or school year?"),  # opening
        _agent_reply("What brings you here?"),  # after first user msg
        # Wrap-up turn with persona payload
        _agent_reply(
            "Got it — let's get started.",
            phase="wrap_up",
            persona={
                "age_band": "13-15",
                "school_level": "lower_secondary",
                "initial_intent": "exam prep",
            },
        ),
    ]
    create = client.post("/persona/create", json={"username": "alice", "confirm": True}).json()
    sid = create["session_id"]

    client.post("/chat", json={"session_id": sid, "message": "I'm in year 10"})
    resp = client.post(
        "/chat", json={"session_id": sid, "message": "got a math exam soon"}
    )
    assert resp.status_code == 200
    assert resp.json()["onboarding_complete"] is True

    # Persona file should now exist.
    from app import persona as persona_mod

    loaded = persona_mod.load_persona("alice")
    assert loaded is not None
    assert loaded.age_band == "13-15"
    assert loaded.initial_intent == "exam prep"

    # A second /persona/create returns 'exists'.
    resp2 = client.post("/persona/create", json={"username": "alice"})
    assert resp2.json()["status"] == "exists"


def test_persona_reset_removes_file(client, fake_openrouter, tmp_persona_dir):
    from app import persona as persona_mod
    from app.session import Persona

    persona_mod.save_persona(
        Persona(username="alice", created_at="2026-05-14T00:00:00Z")
    )
    resp = client.post("/persona/reset", json={"username": "alice"})
    assert resp.status_code == 200
    assert persona_mod.load_persona("alice") is None


# ---- /specializations and /thinking-trace -----------------------------------


def test_list_specializations_excludes_persona(client):
    resp = client.get("/specializations")
    assert resp.status_code == 200
    domains = {entry["domain"] for entry in resp.json()}
    assert "persona" not in domains
    assert "math" in domains
    assert "programming" in domains
    assert "essay" in domains


def test_thinking_trace_returns_expected_shape(client, fake_openrouter):
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply(
            "Initial Socratic q?",
            phase=None,
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.get(f"/session/{new['session_id']}/thinking-trace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "solving"
    assert body["domain"] == "math"
    assert "phase_breakdown" in body
    assert "calibration_points" in body
    assert "reflection_summary" in body


def test_thinking_trace_404_unknown_session(client):
    resp = client.get("/session/nope/thinking-trace")
    assert resp.status_code == 404


# ---- /tools/{name} dispatch endpoint ----------------------------------------


def test_tools_endpoint_backend_dispatch(client, fake_openrouter, monkeypatch):
    """Direct /tools/{name} invocation: bypasses the agent, dispatches the
    backend tool, returns its result."""
    fake = types.ModuleType("specializations.math.tools.algebra")
    fake.run = lambda args, session: {"result": "ok", "display_data": {}}
    monkeypatch.setitem(sys.modules, "specializations.math.tools.algebra", fake)

    fake_openrouter.responses = [_classifier_reply("math"), _agent_reply("clar?")]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/tools/algebra",
        json={"session_id": new["session_id"], "args": {"expression": "x", "operation": "solve"}},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "ok"


def test_tools_endpoint_rejects_frontend_tool(client, fake_openrouter):
    fake_openrouter.responses = [_classifier_reply("programming"), _agent_reply("clar?")]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "print hello"},
    ).json()
    resp = client.post(
        "/tools/code_runner",
        json={"session_id": new["session_id"], "args": {"code": "print(1)"}},
    )
    assert resp.status_code == 400
    assert "frontend" in resp.json()["detail"]


def test_tools_endpoint_404_unknown_tool(client, fake_openrouter):
    fake_openrouter.responses = [_classifier_reply("math"), _agent_reply("clar?")]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/tools/nonexistent",
        json={"session_id": new["session_id"], "args": {}},
    )
    assert resp.status_code == 404


# ---- Auto-injection of CalibrationCheck / ReflectionPrompt directives -------


def test_reflection_prompt_auto_injects_directive(client, fake_openrouter):
    """When agent emits signal.emit_reflection, backend auto-injects a
    ReflectionPrompt ui_directive with a question from the backend bank."""
    from app.chat import REFLECTION_QUESTIONS

    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Take a moment.",
            emit_reflection="periodic",
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "I think I see it"}
    )
    assert resp.status_code == 200
    directives = resp.json()["ui_directives"]
    rp = [d for d in directives if d["component"] == "ReflectionPrompt"]
    assert len(rp) == 1
    assert rp[0]["domain"] == "general"
    assert rp[0]["props"]["trigger"] == "periodic"
    assert rp[0]["props"]["question"] in REFLECTION_QUESTIONS["periodic"]


def test_calibration_check_auto_injects_directive(client, fake_openrouter):
    """When agent emits signal.emit_calibration_check=true, backend auto-injects
    a CalibrationCheck ui_directive with the fixed backend-defined question."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Before you try this part.",
            emit_calibration_check=True,
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "I get the first part"}
    )
    assert resp.status_code == 200
    directives = resp.json()["ui_directives"]
    cc = [d for d in directives if d["component"] == "CalibrationCheck"]
    assert len(cc) == 1
    assert cc[0]["domain"] == "general"
    assert "1 to 5" in cc[0]["props"]["question"]


def test_calibration_check_blocks_wrap_up_on_same_turn(client, fake_openrouter):
    """If agent emits both emit_calibration_check and phase='wrap_up', the phase
    transition is blocked so the student can answer before the session closes."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Before you finish — how confident were you?",
            emit_calibration_check=True,
            phase="wrap_up",  # backend should block this
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "I think I got it"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Phase must NOT be wrap_up — the calibration question is still pending.
    assert body["phase"] != "wrap_up"
    # CalibrationCheck directive must still appear.
    cc = [d for d in body["ui_directives"] if d["component"] == "CalibrationCheck"]
    assert len(cc) == 1


def test_no_double_inject_when_agent_already_emits_directive(client, fake_openrouter):
    """If agent emits signal.emit_reflection AND also manually includes a
    ReflectionPrompt in ui_directives, backend deduplicates — only one directive."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Reflect on that.",
            emit_reflection="periodic",
            # Agent also manually emits the directive (redundant but possible).
            ui_directives=[{
                "component": "ReflectionPrompt",
                "domain": "general",
                "props": {"question": "Already there.", "trigger": "periodic"},
                "placement": "inline",
                "lifetime": "until_next_turn",
            }],
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    resp = client.post(
        "/chat", json={"session_id": new["session_id"], "message": "ok"}
    )
    assert resp.status_code == 200
    rp = [d for d in resp.json()["ui_directives"] if d["component"] == "ReflectionPrompt"]
    assert len(rp) == 1, "Expected exactly one ReflectionPrompt directive, not two"


# ---- signal field integration tests -----------------------------------------


def test_signal_subproblem_updates_applied(client, fake_openrouter):
    """signal.subproblem_updates creates subproblems in session state."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply(
            "Let's break it down.",
            phase="decomposition",
        ),
        _agent_reply(
            "Onto the first part.",
            phase="solving",
            subproblem_updates=[
                {"id": "sp-1", "description": "isolate x", "goal": "get x alone", "status": "active"},
                {"id": "sp-2", "description": "verify", "goal": "check the answer", "status": "pending"},
            ],
            active_subproblem="sp-1",
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "2x+3=7"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "two parts"})
    client.post("/chat", json={"session_id": sid, "message": "looks right"})

    from app import session as session_mod
    s = session_mod.get(sid)
    ids = {sp.id for sp in s.subproblems}
    assert "sp-1" in ids
    assert "sp-2" in ids
    sp1 = next(sp for sp in s.subproblems if sp.id == "sp-1")
    assert sp1.status == "active"
    assert sp1.description == "isolate x"


def test_signal_self_correction_increments_metric(client, fake_openrouter):
    """signal.self_correction_noted increments session.metrics.self_corrections."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply(
            "Nice catch — what made you reconsider?",
            self_correction_noted=True,
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "wait, I was wrong"})

    from app import session as session_mod
    s = session_mod.get(sid)
    assert s.metrics.self_corrections == 1


def test_signal_escape_hatch_marks_subproblem(client, fake_openrouter):
    """signal.escape_hatch_triggered marks the active subproblem and increments metric."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply(
            "Let's start.",
            phase="solving",
            subproblem_updates=[{"id": "sp-1", "description": "isolate x", "status": "active"}],
            active_subproblem="sp-1",
        ),
        _agent_reply(
            "Before I show you — in one sentence, where did your thinking get stuck?",
            escape_hatch_triggered=True,
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "no idea"})
    client.post("/chat", json={"session_id": sid, "message": "just show me"})

    from app import session as session_mod
    s = session_mod.get(sid)
    sp = next((sp for sp in s.subproblems if sp.id == "sp-1"), None)
    assert sp is not None
    assert sp.direct_answer_requested is True
    assert s.metrics.direct_answer_requests == 1


def test_signal_new_scalar_fields_tracked(client, fake_openrouter):
    """verification_prompted, concepts_established, decomposition_source,
    disengagement_noted, refined_query are all persisted from signal."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply(
            "Good, let's proceed.",
            verification_prompted=True,
            concepts_established=["inverse operations", "linear equations"],
            decomposition_source="student",
            disengagement_noted=False,
            refined_query="Solve for x: 2x + 3 = 7",
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "2x+3=7"},
    ).json()
    sid = new["session_id"]

    # Give the session an active subproblem first so verification_prompted records.
    from app import session as session_mod
    s = session_mod.get(sid)
    from app.session import Subproblem
    s.subproblems.append(Subproblem(id="sp-1", description="isolate x", status="active"))
    s.active_subproblem_id = "sp-1"
    session_mod.put(s)

    client.post("/chat", json={"session_id": sid, "message": "I verified it"})

    s = session_mod.get(sid)
    assert "inverse operations" in s.concepts_established
    assert "linear equations" in s.concepts_established
    assert s.decomposition_source == "student"
    assert s.refined_query == "Solve for x: 2x + 3 = 7"
    assert "sp-1" in s.verification_prompted_subproblems


def test_signal_disengagement_counted(client, fake_openrouter):
    """signal.disengagement_noted increments session.disengagement_count."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply("Still there?", disengagement_noted=True),
        _agent_reply("Over to you.", disengagement_noted=True),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "k"})
    client.post("/chat", json={"session_id": sid, "message": "."})

    from app import session as session_mod
    s = session_mod.get(sid)
    assert s.disengagement_count == 2


def test_signal_reflection_quality_attaches_to_pending(client, fake_openrouter):
    """signal.last_reflection_quality on the turn after a reflection response
    attaches the quality rating to the pending reflection entry."""
    from app.chat import REFLECTION_QUESTIONS

    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply("Take a moment.", emit_reflection="periodic"),  # queues reflection
        _agent_reply("Good.", last_reflection_quality="deep"),       # attaches quality
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "Let me think"})
    client.post(
        "/chat",
        json={"session_id": sid, "message": "I noticed I kept assuming x was positive — that's a pattern."},
    )

    from app import session as session_mod
    s = session_mod.get(sid)
    assert len(s.reflection_prompts) == 1
    rp = s.reflection_prompts[0]
    assert rp.trigger == "periodic"
    assert rp.question in REFLECTION_QUESTIONS["periodic"]
    assert rp.quality == "deep"


def test_signal_calibration_outcome_closes_open_point(client, fake_openrouter):
    """signal.calibration_outcome attaches to the most recent open CalibrationPoint."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply("Before you try.", emit_calibration_check=True),
        _agent_reply("Good work.", calibration_outcome="correct"),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]

    from app import session as session_mod
    from app.session import CalibrationPoint, Subproblem
    s = session_mod.get(sid)
    s.subproblems.append(Subproblem(id="sp-1", description="isolate x", status="active"))
    s.active_subproblem_id = "sp-1"
    session_mod.put(s)

    # Turn that emits emit_calibration_check
    client.post("/chat", json={"session_id": sid, "message": "ready"})

    # Student answers the calibration widget
    client.post(
        "/chat",
        json={
            "session_id": sid,
            "directive_response": {"component": "CalibrationCheck", "value": 4},
        },
    )

    s = session_mod.get(sid)
    assert len(s.calibration_points) == 1
    assert s.calibration_points[0].predicted_confidence == 4
    assert s.calibration_points[0].outcome == "correct"


def test_thinking_trace_includes_signal_derived_fields(client, fake_openrouter):
    """refined_query, concepts_established, decomposition_source, and
    disengagement_count all appear in the /thinking-trace response."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply(
            "Let's move on.",
            refined_query="Solve 2x+3=7",
            concepts_established=["linear equations"],
            decomposition_source="student",
            disengagement_noted=True,
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "2x+3=7"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "I understand"})

    resp = client.get(f"/session/{sid}/thinking-trace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["refined_query"] == "Solve 2x+3=7"
    assert "linear equations" in body["concepts_established"]
    assert body["decomposition_source"] == "student"
    assert body["disengagement_count"] == 1


# ---- initial_understanding capture ------------------------------------------


def test_initial_understanding_captured_from_refined_query(
    client, fake_openrouter
):
    """When the agent emits signal.refined_query, initial_understanding is set
    directly from that value — no LLM summariser call."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Got it. Let's plan.",
            phase="decomposition",
            refined_query="I think I just isolate x",
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post(
        "/chat",
        json={"session_id": sid, "message": "I think I just isolate x"},
    )

    from app import session as session_mod
    s = session_mod.get(sid)
    assert s.initial_understanding == "I think I just isolate x"


def test_initial_understanding_capture_is_idempotent(
    client, fake_openrouter
):
    """Once initial_understanding is set from the first refined_query, later
    turns that also emit refined_query must NOT overwrite it."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        # First refined_query — sets initial_understanding.
        _agent_reply(
            "Onto decomposition.",
            phase="decomposition",
            refined_query="I think I just isolate x",
        ),
        # Later turn also emits refined_query — must not overwrite.
        _agent_reply(
            "And solving.",
            phase="solving",
            refined_query="Different framing now",
        ),
        _agent_reply("Wrapping up.", phase="wrap_up"),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "I get it"})
    client.post("/chat", json={"session_id": sid, "message": "next part"})
    client.post("/chat", json={"session_id": sid, "message": "all done"})

    from app import session as session_mod
    s = session_mod.get(sid)
    assert s.initial_understanding == "I think I just isolate x", (
        f"initial_understanding was overwritten to {s.initial_understanding!r}"
    )


def test_initial_understanding_skipped_when_refined_query_absent(
    client, fake_openrouter
):
    """If the agent never emits signal.refined_query, initial_understanding stays None."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply("Tell me more first."),  # no refined_query in signal
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "I'm not sure"})

    from app import session as session_mod
    s = session_mod.get(sid)
    assert s.initial_understanding is None


def test_thinking_trace_surfaces_captured_initial_understanding(
    client, fake_openrouter, monkeypatch
):
    """The /thinking-trace response must include the captured initial_understanding.

    initial_understanding is set from signal.refined_query. final_understanding
    comes from call_summarizer (called inline by /thinking-trace when the session
    hasn't reached wrap_up yet).
    """
    from app import llm as llm_mod

    async def fake_summary(
        initial_understanding, recent_student_messages, session_id="x", temperature=0.3
    ):
        return {
            "final_understanding": "You worked out the inverse-operations step.",
            "delta_label": "moderate",
            "delta_evidence": "You moved from raw isolation to inverse operations.",
        }

    monkeypatch.setattr(llm_mod, "call_summarizer", fake_summary)

    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your initial read?"),
        _agent_reply(
            "Onto decomposition.",
            phase="decomposition",
            refined_query="I came in thinking isolate x",
        ),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    client.post("/chat", json={"session_id": sid, "message": "isolate x"})

    resp = client.get(f"/session/{sid}/thinking-trace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["initial_understanding"] == "I came in thinking isolate x"
    assert body["final_understanding"] == "You worked out the inverse-operations step."
    assert body["understanding_delta_label"] == "moderate"


def test_reflection_directive_question_matches_session_record(client, fake_openrouter):
    """The question shown in the ReflectionPrompt directive must match the
    question stored in session.reflection_prompts — no double random.choice."""
    fake_openrouter.responses = [
        _classifier_reply("math"),
        _agent_reply("What's your read?"),
        _agent_reply("Take a moment.", emit_reflection="wrap_up"),
    ]
    new = client.post(
        "/session/new",
        json={"username": "alice", "mode": "solving", "query": "x+1=2"},
    ).json()
    sid = new["session_id"]
    resp = client.post("/chat", json={"session_id": sid, "message": "All done"})

    from app import session as session_mod
    s = session_mod.get(sid)
    directive_question = next(
        d["props"]["question"]
        for d in resp.json()["ui_directives"]
        if d["component"] == "ReflectionPrompt"
    )
    session_question = s.reflection_prompts[-1].question
    assert directive_question == session_question, (
        "Directive and session record different questions — random.choice called twice"
    )
