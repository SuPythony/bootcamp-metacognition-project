"""Tests for persona file IO and persona_updates merge semantics."""

from __future__ import annotations

import json

import pytest

from app import persona as persona_mod
from app.session import Persona, PersonaField


def test_save_and_load_round_trip(tmp_persona_dir):
    p = Persona(
        username="alice",
        created_at="2026-05-14T00:00:00Z",
        age_band="13-15",
        school_level="lower_secondary",
        initial_intent="pass my math test",
    )
    persona_mod.save_persona(p)
    loaded = persona_mod.load_persona("alice")
    assert loaded is not None
    assert loaded.username == "alice"
    assert loaded.age_band == "13-15"
    assert loaded.initial_intent == "pass my math test"


def test_load_returns_none_when_missing(tmp_persona_dir):
    assert persona_mod.load_persona("nobody") is None


def test_atomic_write_no_corruption_on_existing_file(tmp_persona_dir):
    """Saving over an existing file replaces atomically — old read shouldn't
    return partial content."""
    p1 = Persona(username="alice", created_at="2026-05-14T00:00:00Z", age_band="13-15")
    persona_mod.save_persona(p1)
    p2 = Persona(username="alice", created_at="2026-05-14T00:00:00Z", age_band="16-18")
    persona_mod.save_persona(p2)
    loaded = persona_mod.load_persona("alice")
    assert loaded.age_band == "16-18"


def test_persona_path_rejects_traversal(tmp_persona_dir):
    """Usernames with path separators / dots must be rejected before touching
    the filesystem."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        persona_mod._persona_path("../etc/passwd")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        persona_mod._persona_path("..")

    with pytest.raises(HTTPException):
        persona_mod._persona_path("a/b")


def test_merge_add_to_list(tmp_persona_dir):
    persona_mod.save_persona(
        Persona(username="alice", created_at="2026-05-14T00:00:00Z")
    )
    persona_mod.merge_persona_updates(
        "alice",
        [
            {
                "field": "confident_subjects",
                "operation": "add",
                "value": "linear equations",
                "evidence": "solved sp-1 without hints",
                "inferred": True,
            }
        ],
    )
    loaded = persona_mod.load_persona("alice")
    assert len(loaded.confident_subjects) == 1
    assert loaded.confident_subjects[0].value == "linear equations"
    assert loaded.confident_subjects[0].inferred is True
    assert loaded.confident_subjects[0].evidence == "solved sp-1 without hints"


def test_merge_add_is_idempotent_on_same_value(tmp_persona_dir):
    """Adding the same value twice doesn't create duplicates."""
    persona_mod.save_persona(
        Persona(username="alice", created_at="2026-05-14T00:00:00Z")
    )
    update = [
        {"field": "confident_subjects", "operation": "add", "value": "algebra"}
    ]
    persona_mod.merge_persona_updates("alice", update)
    persona_mod.merge_persona_updates("alice", update)
    loaded = persona_mod.load_persona("alice")
    assert len(loaded.confident_subjects) == 1


def test_merge_remove_from_list(tmp_persona_dir):
    persona_mod.save_persona(
        Persona(
            username="alice",
            created_at="2026-05-14T00:00:00Z",
            confident_subjects=[
                PersonaField(value="algebra", inferred=True),
                PersonaField(value="geometry", inferred=True),
            ],
        )
    )
    persona_mod.merge_persona_updates(
        "alice",
        [{"field": "confident_subjects", "operation": "remove", "value": "algebra"}],
    )
    loaded = persona_mod.load_persona("alice")
    assert [f.value for f in loaded.confident_subjects] == ["geometry"]


def test_merge_set_persona_field(tmp_persona_dir):
    persona_mod.save_persona(
        Persona(username="alice", created_at="2026-05-14T00:00:00Z")
    )
    persona_mod.merge_persona_updates(
        "alice",
        [
            {
                "field": "learning_style",
                "operation": "set",
                "value": "examples_first",
                "inferred": True,
                "evidence": "preferred examples over theory in sp-1",
            }
        ],
    )
    loaded = persona_mod.load_persona("alice")
    assert loaded.learning_style.value == "examples_first"
    assert loaded.learning_style.inferred is True


def test_merge_remove_persona_field(tmp_persona_dir):
    persona_mod.save_persona(
        Persona(
            username="alice",
            created_at="2026-05-14T00:00:00Z",
            learning_style=PersonaField(value="examples_first", inferred=True),
        )
    )
    persona_mod.merge_persona_updates(
        "alice",
        [{"field": "learning_style", "operation": "remove", "value": "examples_first"}],
    )
    loaded = persona_mod.load_persona("alice")
    assert loaded.learning_style is None


def test_merge_set_flat_string(tmp_persona_dir):
    persona_mod.save_persona(
        Persona(username="alice", created_at="2026-05-14T00:00:00Z", age_band="13-15")
    )
    persona_mod.merge_persona_updates(
        "alice",
        [{"field": "age_band", "operation": "set", "value": "16-18"}],
    )
    loaded = persona_mod.load_persona("alice")
    assert loaded.age_band == "16-18"


def test_merge_on_unknown_field_silently_skips(tmp_persona_dir):
    """Defensive: an agent update for a field that doesn't exist on Persona
    must not break the merge."""
    persona_mod.save_persona(
        Persona(username="alice", created_at="2026-05-14T00:00:00Z")
    )
    persona_mod.merge_persona_updates(
        "alice",
        [
            {"field": "favorite_color", "operation": "set", "value": "blue"},
            {"field": "confident_subjects", "operation": "add", "value": "algebra"},
        ],
    )
    loaded = persona_mod.load_persona("alice")
    # The valid update went through.
    assert any(f.value == "algebra" for f in loaded.confident_subjects)
    # No favorite_color attribute exists.
    assert not hasattr(loaded, "favorite_color")


def test_merge_on_missing_persona_returns_none(tmp_persona_dir):
    """If no persona file exists, updates are a no-op (the onboarding session
    is itself in flight; the wrap_up handler builds the stub)."""
    result = persona_mod.merge_persona_updates(
        "noone", [{"field": "confident_subjects", "operation": "add", "value": "x"}]
    )
    assert result is None


def test_handle_persona_wrap_up_writes_stub(tmp_persona_dir):
    persona_mod.handle_persona_wrap_up(
        "alice",
        {
            "age_band": "16-18",
            "school_level": "upper_secondary",
            "initial_intent": "preparing for boards",
        },
    )
    loaded = persona_mod.load_persona("alice")
    assert loaded.age_band == "16-18"
    assert loaded.school_level == "upper_secondary"
    assert loaded.initial_intent == "preparing for boards"
    # No other fields populated.
    assert loaded.confident_subjects == []
    assert loaded.learning_style is None
