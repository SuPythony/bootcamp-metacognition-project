"""In-memory session store and Session model.

Schema matches the "Session State Schema" in CLAUDE.md. Domain enum standardized
on "math" (folder name) — not "mathematics".
"""

from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["math", "programming", "essay", "science", "general", "persona"]
Phase = Literal["clarification", "decomposition", "solving", "wrap_up"]


class Subproblem(BaseModel):
    id: str
    description: str
    goal: str
    status: Literal["pending", "active", "solved"] = "pending"
    hints_given: int = 0
    direct_answer_requested: bool = False


class Metrics(BaseModel):
    turns_total: int = 0
    clarification_turns: int = 0
    decomposition_turns: int = 0
    hints_per_subproblem: list[int] = Field(default_factory=list)
    direct_answer_requests: int = 0
    self_corrections: int = 0
    phase_timestamps: dict[str, str] = Field(default_factory=dict)


class Session(BaseModel):
    session_id: str
    domain: Domain
    original_query: str
    phase: Phase = "clarification"
    initial_understanding: str | None = None
    subproblems: list[Subproblem] = Field(default_factory=list)
    active_subproblem_index: int = 0
    metrics: Metrics = Field(default_factory=Metrics)
    message_history: list[dict] = Field(default_factory=list)

    def to_context_str(self) -> str:
        # Compact JSON-ish summary; full schema documented in CLAUDE.md.
        raise NotImplementedError


# In-memory store. Replace with anything else later — interface kept tiny on purpose.
_SESSIONS: dict[str, Session] = {}


def get(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def put(session: Session) -> None:
    _SESSIONS[session.session_id] = session
