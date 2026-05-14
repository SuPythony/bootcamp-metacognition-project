"""POST /persona/create, POST /persona/reset, plus helpers chat.py uses for
persona file IO and inline persona_updates merging.

Onboarding flow (per CLAUDE.md "Login & Persona Flow"):
  1. Frontend POSTs /persona/create {username}.
  2. If a persona file exists at ${PERSONA_DIR}/<username>.json — return it.
  3. Otherwise, create a Session in domain="persona" mode="solving", run one
     opening turn through the regular tutor pipeline (the persona prompt is
     loaded automatically by the plugin registry), and return the session_id
     so the frontend continues the 2-turn intake via /chat.
  4. On the persona session's wrap_up turn the agent emits a `persona`
     payload; chat.py calls handle_persona_wrap_up to write the stub to disk.

Files are written atomically (write to tmp + rename) so a crash mid-write
can't corrupt the user's persona.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import llm
from app import session as session_mod
from app.session import Persona, PersonaField, Session

router = APIRouter()


def _persona_dir() -> Path:
    """Read PERSONA_DIR from env each call so tests can monkeypatch it."""
    path = Path(os.environ.get("PERSONA_DIR", "./personas")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _persona_path(username: str) -> Path:
    # Basic safety: no path traversal, no separators.
    if "/" in username or "\\" in username or username in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail=f"Invalid username: {username!r}")
    return _persona_dir() / f"{username}.json"


def load_persona(username: str) -> Persona | None:
    """Load and return a Persona, or None if the file does not exist."""
    path = _persona_path(username)
    if not path.exists():
        return None
    return Persona.model_validate_json(path.read_text())


def save_persona(persona: Persona) -> None:
    """Atomic write: write to tmpfile in the same dir, fsync, rename over."""
    dir_ = _persona_dir()
    payload = persona.model_dump_json(indent=2)
    # NamedTemporaryFile in the same dir so the rename is atomic on POSIX.
    fd, tmp_name = tempfile.mkstemp(prefix=f".{persona.username}.", suffix=".tmp", dir=dir_)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, dir_ / f"{persona.username}.json")
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def merge_persona_updates(username: str, updates: list[dict]) -> Persona | None:
    """Apply a list of persona_updates to the on-disk persona file.

    Each update has shape:
        { field, operation: "add" | "remove" | "set", value, evidence?, inferred? }

    Updates against a user with no persona file on disk are no-ops (the
    persona-onboarding session is itself building the stub; updates only
    apply post-onboarding). Returns the updated persona, or None if there
    was nothing to update.
    """
    persona = load_persona(username)
    if persona is None:
        return None

    for upd in updates:
        field = upd.get("field")
        op = upd.get("operation", "set")
        value = upd.get("value")
        evidence = upd.get("evidence")
        inferred = upd.get("inferred", True)
        if not field or value is None:
            continue
        if not hasattr(persona, field):
            continue  # unknown field — silently skip (defensive)

        current = getattr(persona, field)
        if isinstance(current, list):
            # list-valued: confident_subjects, difficult_subjects.
            if op == "add":
                if not any(
                    isinstance(item, PersonaField) and item.value == value
                    for item in current
                ):
                    current.append(
                        PersonaField(value=value, inferred=inferred, evidence=evidence)
                    )
            elif op == "remove":
                setattr(
                    persona,
                    field,
                    [
                        item
                        for item in current
                        if not (isinstance(item, PersonaField) and item.value == value)
                    ],
                )
            elif op == "set":
                setattr(
                    persona,
                    field,
                    [PersonaField(value=value, inferred=inferred, evidence=evidence)],
                )
        elif isinstance(current, PersonaField) or current is None:
            # PersonaField-valued: learning_style, preferred_pace, goals, education_detail.
            if op in {"set", "add"}:
                setattr(
                    persona,
                    field,
                    PersonaField(value=value, inferred=inferred, evidence=evidence),
                )
            elif op == "remove":
                setattr(persona, field, None)
        else:
            # Flat string fields (age_band, school_level, initial_intent): allow set only.
            if op == "set":
                setattr(persona, field, value)

    save_persona(persona)
    return persona


def handle_persona_wrap_up(username: str, persona_payload: dict[str, Any]) -> Persona:
    """Build a Persona from the agent's wrap_up payload and write it to disk.

    The payload may include any subset of:
        { age_band, school_level, initial_intent, education_detail, ... }

    The persona prompt currently only emits age_band, school_level,
    initial_intent (the 2-turn intake produces a stub). All other fields
    accumulate post-onboarding via merge_persona_updates.
    """
    created_at = persona_payload.get(
        "created_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    persona = Persona(
        username=username,
        created_at=created_at,
        age_band=persona_payload.get("age_band"),
        school_level=persona_payload.get("school_level"),
        initial_intent=persona_payload.get("initial_intent"),
    )
    save_persona(persona)
    # Cleanup the onboarding session since it's no longer needed.
    return persona


# ---- Routes -----------------------------------------------------------------


class PersonaCreateRequest(BaseModel):
    username: str


class PersonaCreateResponse(BaseModel):
    status: str
    session_id: str | None = None
    persona: Persona | None = None
    opening_message: str | None = None


class PersonaResetResponse(BaseModel):
    status: str


@router.post("/persona/create", response_model=PersonaCreateResponse)
async def persona_create(req: PersonaCreateRequest) -> PersonaCreateResponse:
    """Either return an existing persona or kick off an onboarding session.

    On 'pending', we also return the agent's opening_message so the frontend
    can immediately render Turn 1 of the intake without an extra /chat call.
    This is a small contract extension beyond the doc's stated response shape.
    """
    existing = load_persona(req.username)
    if existing is not None:
        return PersonaCreateResponse(status="exists", persona=existing)

    # Create a persona-domain session and run the opening turn.
    session = Session(
        session_id=str(uuid.uuid4()),
        username=req.username,
        mode="solving",
        domain="persona",
        original_query="(onboarding)",
        message_history=[
            # The agent leads the persona interview, so we seed a user-side
            # "hi" so the LLM call doesn't start from a system-only prompt.
            {"role": "user", "content": "Hi, I just opened the app."},
        ],
    )
    session_mod.put(session)

    # Defer the actual opening LLM call to avoid an import-time circular
    # dependency on chat (chat imports persona).
    from app.chat import _apply_agent_response, _run_chat_turn, _validate_phase

    parsed, _, _ = await _run_chat_turn(session)
    session.phase = _validate_phase(session, parsed.control.phase)
    _apply_agent_response(session, parsed)
    session.message_history.append({"role": "assistant", "content": parsed.reply})
    session_mod.put(session)

    return PersonaCreateResponse(
        status="pending",
        session_id=session.session_id,
        opening_message=parsed.reply,
    )


@router.post("/persona/reset", response_model=PersonaResetResponse)
async def persona_reset(req: PersonaCreateRequest) -> PersonaResetResponse:
    path = _persona_path(req.username)
    if path.exists():
        path.unlink()
    return PersonaResetResponse(status="reset")
