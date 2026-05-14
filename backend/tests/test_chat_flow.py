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


def _agent_reply(reply: str, **control_overrides) -> str:
    """Build a single JSON-encoded agent response. Convenience for queueing
    responses into fake_openrouter."""
    return json.dumps({"reply": reply, "control": control_overrides})


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


def test_chat_rejects_illegal_phase_jump(client, fake_openrouter):
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
    assert resp.status_code == 400
    assert "Illegal phase transition" in resp.json()["detail"]


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
    # backend_tool_result is surfaced.
    assert body["backend_tool_result"] is not None
    assert body["backend_tool_result"]["name"] == "algebra"


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
    assert body["backend_tool_result"] is None


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
    resp = client.post("/persona/create", json={"username": "alice"})
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
    create = client.post("/persona/create", json={"username": "alice"}).json()
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
