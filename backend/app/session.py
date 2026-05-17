"""In-memory session store and Session model.

Schema mirrors "Session State Schema" in CLAUDE.md. Domain enum standardised on
"math" (folder name). The model carries fields needed for v1.1 (critique mode,
artifact, critique_findings) as nullable so the schema is forward-compatible —
the v1 /session/new endpoint still rejects `mode != "solving"`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Domain = Literal["math", "programming", "essay", "science", "general", "persona"]
Mode = Literal["solving", "critique"]
Phase = Literal[
    "clarification", "decomposition", "solving", "critique", "synthesis", "wrap_up"
]


# Legal phase transitions, keyed by (mode, domain_is_persona).
# Persona onboarding has its own minimal machine (clarification → wrap_up).
# Solving / critique use the standard sequences.
_PHASE_TRANSITIONS: dict[tuple[str, bool], dict[str, set[str]]] = {
    ("solving", False): {
        "clarification": {"clarification", "decomposition"},
        "decomposition": {"decomposition", "solving"},
        "solving": {"solving", "wrap_up"},
        "wrap_up": {"wrap_up"},
    },
    ("critique", False): {
        "clarification": {"clarification", "critique"},
        "critique": {"critique", "synthesis"},
        "synthesis": {"synthesis", "wrap_up"},
        "wrap_up": {"wrap_up"},
    },
    # Persona onboarding sits inside mode="solving" but uses its own phase set.
    ("solving", True): {
        "clarification": {"clarification", "wrap_up"},
        "wrap_up": {"wrap_up"},
    },
}


def legal_next_phase(mode: str, domain: str, current: str, proposed: str) -> bool:
    """Return True if a transition from `current` to `proposed` is legal for
    a session in the given mode/domain. Used by the backend phase validator."""
    key = (mode, domain == "persona")
    transitions = _PHASE_TRANSITIONS.get(key)
    if transitions is None:
        return False
    return proposed in transitions.get(current, set())


class Subproblem(BaseModel):
    id: str
    description: str
    goal: str = ""
    status: Literal["pending", "active", "solved"] = "pending"
    hints_given: int = 0
    direct_answer_requested: bool = False
    escape_hatch_reflection: str | None = None
    confidence_score: int | None = None


class CritiqueFinding(BaseModel):
    """Populated only in critique mode (v1.1)."""

    id: str
    claim: str
    kind: Literal[
        "factual_error",
        "reasoning_gap",
        "missing_step",
        "overconfident_language",
        "other",
    ] = "other"
    verified: bool = False
    was_self_corrected: bool = False


class CalibrationPoint(BaseModel):
    subproblem_id: str
    predicted_confidence: int
    outcome: Literal["correct", "wrong", "partial"] | None = None
    noted_at: str | None = None


class ReflectionPrompt(BaseModel):
    trigger: Literal["periodic", "self_correction", "escape_hatch", "wrap_up"]
    question: str
    response: str | None = None
    quality: Literal["shallow", "decent", "deep"] | None = None


class PersonaField(BaseModel):
    """Wrapper for inferred persona fields. Onboarding-captured fields and
    metadata stay as plain strings; everything else is wrapped to flag whether
    the value was directly stated or inferred from session behaviour."""

    value: str
    inferred: bool = True
    evidence: str | None = None


class Persona(BaseModel):
    username: str
    created_at: str
    # Onboarding-captured (flat strings):
    age_band: str | None = None
    school_level: str | None = None
    initial_intent: str | None = None
    # Inferred / structured:
    education_detail: PersonaField | None = None
    confident_subjects: list[PersonaField] = Field(default_factory=list)
    difficult_subjects: list[PersonaField] = Field(default_factory=list)
    learning_style: PersonaField | None = None
    preferred_pace: PersonaField | None = None
    goals: PersonaField | None = None

    def to_context_str(self) -> str:
        """Compact natural-language summary for system-prompt injection."""
        bits: list[str] = []
        if self.age_band:
            bits.append(f"Age band: {self.age_band}.")
        if self.school_level:
            bits.append(f"School level: {self.school_level}.")
        if self.initial_intent:
            bits.append(f"They came here saying: {self.initial_intent!r}.")
        if self.confident_subjects:
            vals = ", ".join(f.value for f in self.confident_subjects)
            tag = "inferred" if all(f.inferred for f in self.confident_subjects) else "stated"
            bits.append(f"Confident ({tag}): {vals}.")
        if self.difficult_subjects:
            vals = ", ".join(f.value for f in self.difficult_subjects)
            tag = "inferred" if all(f.inferred for f in self.difficult_subjects) else "stated"
            bits.append(f"Finds difficult ({tag}): {vals}.")
        for label, field in (
            ("Education", self.education_detail),
            ("Learning style", self.learning_style),
            ("Pace", self.preferred_pace),
            ("Goal", self.goals),
        ):
            if field is not None:
                tag = "inferred" if field.inferred else "stated"
                bits.append(f"{label} ({tag}): {field.value}.")
        return " ".join(bits) if bits else "No persona on file yet."


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: dict) -> None:
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)


class Metrics(BaseModel):
    turns_total: int = 0
    clarification_turns: int = 0
    decomposition_turns: int = 0
    hints_per_subproblem: dict[str, int] = Field(default_factory=dict)
    direct_answer_requests: int = 0
    self_corrections: int = 0
    phase_timestamps: dict[str, str] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class Session(BaseModel):
    session_id: str
    username: str
    mode: Mode = "solving"
    domain: Domain
    original_query: str
    artifact: str | None = None  # populated in critique mode (v1.1)
    phase: Phase = "clarification"
    initial_understanding: str | None = None
    initial_critique: str | None = None
    subproblems: list[Subproblem] = Field(default_factory=list)
    active_subproblem_id: str | None = None
    critique_findings: list[CritiqueFinding] = Field(default_factory=list)
    calibration_points: list[CalibrationPoint] = Field(default_factory=list)
    reflection_prompts: list[ReflectionPrompt] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    message_history: list[dict] = Field(default_factory=list)
    # Last reflection_prompt the agent emitted, awaiting the student's response
    # so we can attach `response` and `quality` on the next turn.
    pending_reflection_index: int | None = None
    # Number of finalized turns since the student's response was attached to the
    # pending reflection but the agent hasn't emitted last_reflection_quality yet.
    # Bumped in `chat()` when a free-text response is attached; reset to 0 when
    # quality is recorded or a new reflection is queued. Drives the
    # `_maybe_force_reflection_quality` safety net.
    pending_reflection_response_turns: int = 0
    # Last frontend tool_call surfaced to the client, awaiting tool_result on
    # the next /chat call.
    pending_frontend_tool: dict | None = None
    # Signal-derived session state (new schema).
    concepts_established: list[str] = Field(default_factory=list)
    student_questions: list[dict] = Field(default_factory=list)
    decomposition_source: Literal["student", "tutor"] | None = None
    disengagement_count: int = 0
    refined_query: str | None = None
    verification_prompted_subproblems: list[str] = Field(default_factory=list)
    # Wrap-up summariser output — stored once at wrap_up entry, served by /thinking-trace.
    final_understanding: str | None = None
    understanding_delta_label: str | None = None
    understanding_delta_evidence: str | None = None
    wrap_up_summary_complete: bool = False

    def active_subproblem(self) -> Subproblem | None:
        if self.active_subproblem_id is None:
            return None
        for sp in self.subproblems:
            if sp.id == self.active_subproblem_id:
                return sp
        return None

    def current_hint_level(self) -> int:
        """Hint level for the currently active subproblem (0 if none active)."""
        sp = self.active_subproblem()
        return sp.hints_given if sp else 0

    def to_context_str(self) -> str:
        """Compact JSON-ish summary the agent reads each turn. Includes the
        current phase, active subproblem, hint state, and the student's
        initial understanding so the prompt doesn't have to re-derive them."""
        import json as _json

        payload: dict[str, Any] = {
            "mode": self.mode,
            "domain": self.domain,
            "phase": self.phase,
            "active_subproblem": self.active_subproblem_id,
            "current_hint_level": self.current_hint_level(),
            "subproblems": [
                {
                    "id": s.id,
                    "description": s.description,
                    "goal": s.goal,
                    "status": s.status,
                    "hints_given": s.hints_given,
                    "direct_answer_requested": s.direct_answer_requested,
                }
                for s in self.subproblems
            ],
            "self_corrections": self.metrics.self_corrections,
            "turns_total": self.metrics.turns_total,
            "initial_understanding": self.initial_understanding,
            "refined_query": self.refined_query,
            "concepts_established": self.concepts_established,
        }
        if self.mode == "critique":
            payload["initial_critique"] = self.initial_critique
            payload["critique_findings"] = [
                {"id": f.id, "claim": f.claim, "verified": f.verified}
                for f in self.critique_findings
            ]
        if self.pending_reflection_index is not None:
            payload["awaiting_reflection_response"] = True
        return _json.dumps(payload, ensure_ascii=False)


# Process-local in-memory store. The deployment doc constrains uvicorn to one
# worker for this reason — replacing this with shared storage is a v2 concern.
_SESSIONS: dict[str, Session] = {}


def get(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def put(session: Session) -> None:
    _SESSIONS[session.session_id] = session


def delete(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def reset_store() -> None:
    """Clear the in-memory store. Test helper; not used in production code."""
    _SESSIONS.clear()
