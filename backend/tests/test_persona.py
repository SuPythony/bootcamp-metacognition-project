"""Tests for /persona/create confirm_new typo-recovery flow."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(fake_openrouter, loaded_registry, tmp_persona_dir):
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_persona_create_new_user_returns_confirm_new(client):
    resp = client.post("/persona/create", json={"username": "brandnewuser"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirm_new"
    assert data.get("session_id") is None


def test_persona_create_confirmed_new_user_returns_pending(client, fake_openrouter):
    reply = {
        "thinking": "",
        "reply": "Hi! What year are you in?",
        "control": {
            "phase": "clarification",
            "active_subproblem": None,
            "hint_level": None,
            "tool_call": None,
            "ui_directives": [],
        },
        "signal": {},
    }
    import json
    fake_openrouter.responses = [json.dumps(reply)]

    resp = client.post("/persona/create", json={"username": "brandnewuser", "confirm": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["session_id"] is not None
    assert data["opening_message"] is not None


def test_persona_create_existing_user_returns_exists(client, tmp_persona_dir):
    from app.persona import save_persona
    from app.session import Persona

    persona = Persona(username="olduser", created_at="2026-01-01T00:00:00Z")
    save_persona(persona)

    resp = client.post("/persona/create", json={"username": "olduser"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "exists"
