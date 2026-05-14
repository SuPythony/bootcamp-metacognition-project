"""Tests for the Session model, phase validator, and in-memory store."""

from __future__ import annotations

import json

import pytest

from app import session as session_mod
from app.session import (
    Persona,
    PersonaField,
    Session,
    Subproblem,
    legal_next_phase,
)


def _session(**overrides) -> Session:
    defaults = dict(
        session_id="s1",
        username="alice",
        mode="solving",
        domain="math",
        original_query="solve 2x+3=7",
    )
    defaults.update(overrides)
    return Session(**defaults)


# ---- Phase validator ---------------------------------------------------------


def test_solving_legal_transitions():
    assert legal_next_phase("solving", "math", "clarification", "decomposition")
    assert legal_next_phase("solving", "math", "decomposition", "solving")
    assert legal_next_phase("solving", "math", "solving", "wrap_up")
    # Staying in the same phase is allowed.
    assert legal_next_phase("solving", "math", "solving", "solving")


def test_solving_illegal_skips():
    # Cannot skip from clarification straight to solving or wrap_up.
    assert not legal_next_phase("solving", "math", "clarification", "solving")
    assert not legal_next_phase("solving", "math", "clarification", "wrap_up")
    # Cannot go backwards.
    assert not legal_next_phase("solving", "math", "solving", "clarification")
    # Cannot leave wrap_up.
    assert not legal_next_phase("solving", "math", "wrap_up", "solving")


def test_persona_uses_minimal_phase_machine():
    """Persona onboarding only walks clarification → wrap_up."""
    assert legal_next_phase("solving", "persona", "clarification", "wrap_up")
    assert legal_next_phase("solving", "persona", "clarification", "clarification")
    # Persona never goes through decomposition or solving phases.
    assert not legal_next_phase("solving", "persona", "clarification", "decomposition")
    assert not legal_next_phase("solving", "persona", "clarification", "solving")


def test_critique_machine_documented_even_if_not_in_v1_runtime():
    """v1.1-ready: the validator knows critique's legal transitions even if
    /session/new currently rejects mode='critique'."""
    assert legal_next_phase("critique", "math", "clarification", "critique")
    assert legal_next_phase("critique", "math", "critique", "synthesis")
    assert legal_next_phase("critique", "math", "synthesis", "wrap_up")
    # Mixing modes is illegal.
    assert not legal_next_phase("critique", "math", "clarification", "decomposition")


# ---- Session.to_context_str --------------------------------------------------


def test_to_context_str_includes_phase_and_active_subproblem():
    s = _session(
        phase="solving",
        subproblems=[
            Subproblem(id="sp-1", description="isolate x", status="active", hints_given=2),
            Subproblem(id="sp-2", description="check answer", status="pending"),
        ],
        active_subproblem_id="sp-1",
        initial_understanding="I think I need to isolate x",
    )
    ctx = json.loads(s.to_context_str())
    assert ctx["phase"] == "solving"
    assert ctx["active_subproblem"] == "sp-1"
    assert ctx["current_hint_level"] == 2
    assert ctx["initial_understanding"] == "I think I need to isolate x"
    assert {sp["id"] for sp in ctx["subproblems"]} == {"sp-1", "sp-2"}


def test_to_context_str_no_active_subproblem():
    s = _session(phase="clarification")
    ctx = json.loads(s.to_context_str())
    assert ctx["active_subproblem"] is None
    assert ctx["current_hint_level"] == 0


def test_to_context_str_critique_mode_adds_critique_fields():
    s = _session(mode="critique", phase="critique", initial_critique="seems suspicious")
    ctx = json.loads(s.to_context_str())
    assert ctx["initial_critique"] == "seems suspicious"
    assert "critique_findings" in ctx


def test_to_context_str_solving_mode_omits_critique_fields():
    s = _session(mode="solving")
    ctx = json.loads(s.to_context_str())
    assert "initial_critique" not in ctx
    assert "critique_findings" not in ctx


# ---- Hint level surface ------------------------------------------------------


def test_current_hint_level_reflects_active_subproblem():
    s = _session(
        subproblems=[
            Subproblem(id="sp-1", description="d", hints_given=3, status="active"),
            Subproblem(id="sp-2", description="d", hints_given=5, status="pending"),
        ],
        active_subproblem_id="sp-1",
    )
    assert s.current_hint_level() == 3
    s.active_subproblem_id = "sp-2"
    assert s.current_hint_level() == 5
    s.active_subproblem_id = None
    assert s.current_hint_level() == 0


# ---- In-memory store ---------------------------------------------------------


def test_store_round_trip():
    s = _session()
    session_mod.put(s)
    fetched = session_mod.get("s1")
    assert fetched is s
    assert session_mod.get("missing") is None


def test_store_delete():
    s = _session()
    session_mod.put(s)
    session_mod.delete("s1")
    assert session_mod.get("s1") is None


def test_reset_store():
    session_mod.put(_session())
    session_mod.put(_session(session_id="s2"))
    session_mod.reset_store()
    assert session_mod.get("s1") is None
    assert session_mod.get("s2") is None


# ---- Persona model -----------------------------------------------------------


def test_persona_to_context_str_minimal():
    p = Persona(
        username="alice",
        created_at="2026-05-14T00:00:00Z",
        age_band="13-15",
        school_level="lower_secondary",
        initial_intent="I want to pass my math test",
    )
    ctx = p.to_context_str()
    assert "13-15" in ctx
    assert "lower_secondary" in ctx
    assert "pass my math test" in ctx


def test_persona_to_context_str_with_inferred_fields():
    p = Persona(
        username="alice",
        created_at="2026-05-14T00:00:00Z",
        confident_subjects=[
            PersonaField(value="linear equations", inferred=True, evidence="solved sp-1 without hints"),
        ],
        learning_style=PersonaField(value="examples_first", inferred=True),
    )
    ctx = p.to_context_str()
    assert "Confident (inferred)" in ctx
    assert "linear equations" in ctx
    assert "Learning style (inferred)" in ctx


def test_persona_to_context_str_empty():
    p = Persona(username="alice", created_at="2026-05-14T00:00:00Z")
    assert p.to_context_str() == "No persona on file yet."


def test_persona_field_distinguishes_inferred_from_stated():
    """The {value, inferred, evidence} shape exists so the agent can treat
    inferred values as hypotheses. Tag is 'stated' when inferred=False."""
    p = Persona(
        username="alice",
        created_at="2026-05-14T00:00:00Z",
        goals=PersonaField(value="ace the exam", inferred=False),
    )
    assert "Goal (stated): ace the exam" in p.to_context_str()
