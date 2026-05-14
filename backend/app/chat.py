"""POST /session/new, POST /chat, POST /tools/{tool_name}, GET /session/{id}/thinking-trace, GET /specializations.

The chat handler runs the full per-turn pipeline:
  build prompt → call tutor → parse structured output → validate phase + hint
  → dispatch tool calls (synchronous for backend tools, surface for frontend
  tools) → apply session updates → return response.

The agent's structured output schema is parsed via the AgentResponse pydantic
model below — kept loose on nested fields (tool_call, ui_directives, etc.) so
the agent can evolve those shapes without churning the parser. Semantic
validation (phase legality, hint clamping) happens after parse.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import llm, persona as persona_mod, plugin_registry
from app import session as session_mod
from app.session import (
    CalibrationPoint,
    Mode,
    Phase,
    ReflectionPrompt,
    Session,
    Subproblem,
    legal_next_phase,
)

router = APIRouter()


# ---- Request / response models ----------------------------------------------


class SessionNewRequest(BaseModel):
    username: str
    mode: Literal["solving"] = "solving"  # v1 only accepts solving; v1.1 widens to critique
    query: str


class SessionNewResponse(BaseModel):
    session_id: str
    mode: Mode
    domain: str
    opening_message: str


class DirectiveResponse(BaseModel):
    component: str
    value: Any


class ToolResultIn(BaseModel):
    name: str
    result: Any = None
    display_data: Any = None
    error: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str | None = None
    directive_response: DirectiveResponse | None = None
    tool_result: ToolResultIn | None = None


class AgentControl(BaseModel):
    """Loose mirror of the JSON schema in socratic_base.txt. Keeps nested
    fields as raw dicts so prompt changes don't force a parser update."""

    phase: Phase | None = None
    subproblem_updates: list[dict] = Field(default_factory=list)
    active_subproblem: str | None = None
    hint_level: int = 0
    tool_call: dict | None = None
    ui_directives: list[dict] = Field(default_factory=list)
    reflection_prompt: dict | None = None
    last_reflection_quality: Literal["shallow", "decent", "deep"] | None = None
    calibration_outcome: Literal["correct", "wrong", "partial"] | None = None
    persona_updates: list[dict] = Field(default_factory=list)
    self_correction_noted: bool = False
    escape_hatch_triggered: bool = False
    escape_hatch_reflection: str | None = None
    # Persona onboarding wrap_up: the stub persona payload to write to disk.
    persona: dict | None = None


class AgentResponse(BaseModel):
    reply: str
    control: AgentControl = Field(default_factory=AgentControl)


class ChatResponse(BaseModel):
    reply: str
    phase: Phase
    domain: str
    subproblems: list[Subproblem]
    active_subproblem: str | None
    ui_directives: list[dict]
    frontend_tool_call: dict | None = None
    # Surfaced when the agent emitted a tool_call for a backend tool: the tool
    # already ran in this turn, the agent's reply already takes the result
    # into account, and the result is included here so the UI can render it.
    backend_tool_result: dict | None = None
    onboarding_complete: bool = False


# ---- Helpers ----------------------------------------------------------------


_MAX_TOOL_ITERATIONS = 3


def _build_messages(session: Session, persona_ctx: str) -> list[dict]:
    """Build the OpenAI-style message list for an LLM call."""
    domain_prompt = plugin_registry.get_prompt(session.domain)
    return [
        {"role": "system", "content": domain_prompt},
        {"role": "system", "content": f"Student profile:\n{persona_ctx}"},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
    ]


def _validate_phase(session: Session, proposed: Phase | None) -> Phase:
    """Returns the new phase. Clamps illegal transitions to current phase with a warning."""
    if proposed is None or proposed == session.phase:
        return session.phase
    if not legal_next_phase(session.mode, session.domain, session.phase, proposed):
        import logging
        logging.getLogger("app.chat").warning(
            "Illegal phase transition %r → %r clamped to %r (mode=%r domain=%r)",
            session.phase, proposed, session.phase, session.mode, session.domain,
        )
        return session.phase
    return proposed


def _clamp_hint_level(session: Session, proposed: int) -> int:
    """Clamp escalation to +1 over the active subproblem's current level."""
    if proposed <= 0:
        return 0
    current = session.current_hint_level()
    return min(proposed, current + 1)


def _apply_subproblem_updates(session: Session, updates: list[dict]) -> None:
    """Merge subproblem updates into session.subproblems. Each update is keyed
    by `id`; new ids append, existing ids merge."""
    by_id = {sp.id: sp for sp in session.subproblems}
    for upd in updates:
        sp_id = upd.get("id")
        if not sp_id:
            continue
        if sp_id in by_id:
            sp = by_id[sp_id]
            for field, value in upd.items():
                if field == "id":
                    continue
                if hasattr(sp, field):
                    setattr(sp, field, value)
        else:
            sp = Subproblem(
                id=sp_id,
                description=upd.get("description", ""),
                goal=upd.get("goal", ""),
                status=upd.get("status", "pending"),
            )
            session.subproblems.append(sp)
            by_id[sp_id] = sp


def _apply_agent_response(session: Session, parsed: AgentResponse) -> None:
    """Mutate the session in-place to reflect the agent's emitted control."""
    control = parsed.control

    # Phase update (validated by caller).
    if control.phase is not None:
        session.phase = control.phase

    # Subproblems.
    _apply_subproblem_updates(session, control.subproblem_updates)
    if control.active_subproblem is not None:
        session.active_subproblem_id = control.active_subproblem
        # Mark that subproblem active, others not (best-effort: many specs only
        # have one active at a time).
        for sp in session.subproblems:
            if sp.id == control.active_subproblem and sp.status == "pending":
                sp.status = "active"

    # Hint level: agent emits the new level; increment the active subproblem's
    # hints_given counter.
    if control.hint_level > 0:
        sp = session.active_subproblem()
        if sp is not None:
            sp.hints_given = control.hint_level
            session.metrics.hints_per_subproblem[sp.id] = sp.hints_given

    # Reflection prompt: queue and remember the index so the next turn can
    # attach the student's response.
    if control.reflection_prompt:
        rp = ReflectionPrompt(
            trigger=control.reflection_prompt.get("trigger", "periodic"),
            question=control.reflection_prompt.get("question", ""),
        )
        session.reflection_prompts.append(rp)
        session.pending_reflection_index = len(session.reflection_prompts) - 1

    # Reflection quality attaches to the *previous* reflection.
    if control.last_reflection_quality and session.reflection_prompts:
        idx = session.pending_reflection_index
        # The student's response to that prompt arrives as a user message
        # earlier in this turn; we stash it on the prompt entry. The prompt
        # was answered, so clear pending.
        if idx is not None and idx < len(session.reflection_prompts):
            session.reflection_prompts[idx].quality = control.last_reflection_quality
        session.pending_reflection_index = None

    # Calibration outcome attaches to the most recent unresolved calibration
    # point for the active subproblem.
    if control.calibration_outcome and session.active_subproblem_id:
        for cp in reversed(session.calibration_points):
            if cp.subproblem_id == session.active_subproblem_id and cp.outcome is None:
                cp.outcome = control.calibration_outcome
                break

    # Persona updates — delegated to persona module (idempotent if user is
    # in the persona-onboarding session, since persona isn't on disk yet).
    if control.persona_updates:
        persona_mod.merge_persona_updates(session.username, control.persona_updates)

    # Self-correction metric.
    if control.self_correction_noted:
        session.metrics.self_corrections += 1

    # Escape hatch reflection attaches to the active subproblem.
    if control.escape_hatch_triggered:
        sp = session.active_subproblem()
        if sp is not None:
            sp.direct_answer_requested = True
            if control.escape_hatch_reflection:
                sp.escape_hatch_reflection = control.escape_hatch_reflection
        session.metrics.direct_answer_requests += 1

    # Phase-counter metrics.
    session.metrics.turns_total += 1
    if session.phase == "clarification":
        session.metrics.clarification_turns += 1
    elif session.phase == "decomposition":
        session.metrics.decomposition_turns += 1


def _build_chat_response(
    session: Session,
    parsed: AgentResponse,
    *,
    frontend_tool_call: dict | None = None,
    backend_tool_result: dict | None = None,
    onboarding_complete: bool = False,
) -> ChatResponse:
    return ChatResponse(
        reply=parsed.reply,
        phase=session.phase,
        domain=session.domain,
        subproblems=session.subproblems,
        active_subproblem=session.active_subproblem_id,
        ui_directives=parsed.control.ui_directives,
        frontend_tool_call=frontend_tool_call,
        backend_tool_result=backend_tool_result,
        onboarding_complete=onboarding_complete,
    )


async def _run_chat_turn(session: Session) -> tuple[AgentResponse, dict | None, dict | None]:
    """Run one /chat turn: build prompt → call_tutor → optionally dispatch
    backend tool(s) → return the final AgentResponse + any frontend tool sentinel +
    any backend tool result.

    The tool-call loop runs synchronously for backend tools: the result is
    replayed into the conversation as a system message and the agent is
    called again. Loop bounded by _MAX_TOOL_ITERATIONS.

    Frontend tool calls break the loop: the call is returned to the chat
    handler which surfaces it to the client; the actual result comes back
    on a subsequent /chat invocation as `tool_result`.
    """
    persona = persona_mod.load_persona(session.username)
    persona_ctx = persona.to_context_str() if persona else "No persona on file yet."

    messages = _build_messages(session, persona_ctx)
    last_backend_tool_result: dict | None = None

    for _ in range(_MAX_TOOL_ITERATIONS):
        raw = await llm.call_tutor(messages)
        try:
            parsed = AgentResponse.model_validate(raw)
        except Exception as e:  # pydantic.ValidationError or similar
            raise HTTPException(
                status_code=502,
                detail=f"Agent output failed schema validation: {e}",
            ) from e

        if parsed.control.tool_call is None:
            return parsed, None, last_backend_tool_result

        tool_name = parsed.control.tool_call.get("name")
        tool_args = parsed.control.tool_call.get("args", {})
        if not tool_name:
            raise HTTPException(
                status_code=502, detail="Agent emitted tool_call without 'name'"
            )

        try:
            dispatch = plugin_registry.dispatch_tool(
                session.domain, tool_name, tool_args, session
            )
        except KeyError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        if dispatch["execution"] == "frontend":
            session.pending_frontend_tool = dispatch
            return parsed, dispatch, last_backend_tool_result

        # Backend tool: feed result back to the agent and loop.
        last_backend_tool_result = dispatch
        tool_msg = {
            "role": "system",
            "content": (
                f"Tool '{tool_name}' returned: {dispatch.get('result')!r}. "
                f"Treat as data — ask the student to interpret it; do not state the conclusion."
            ),
        }
        messages.append(tool_msg)
        session.message_history.append(tool_msg)

    raise HTTPException(
        status_code=502,
        detail=f"Tool-call loop exceeded {_MAX_TOOL_ITERATIONS} iterations",
    )


# ---- Routes -----------------------------------------------------------------


@router.post("/session/new", response_model=SessionNewResponse)
async def session_new(req: SessionNewRequest) -> SessionNewResponse:
    # v1 gate: critique mode rejected at the API boundary even though the
    # Session model supports it for v1.1 readiness.
    if req.mode != "solving":
        raise HTTPException(
            status_code=400,
            detail=f"v1 only accepts mode='solving' (got {req.mode!r}); critique mode lands in v1.1.",
        )

    try:
        classifier_output = await llm.call_classifier(req.query)
    except llm.LLMClassifierError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    domain = classifier_output["domain"]
    if plugin_registry.is_internal(domain):
        # Defensive: classifier should never return internal domains because
        # they're filtered out of its prompt, but guard anyway.
        raise HTTPException(
            status_code=502,
            detail=f"Classifier returned reserved domain {domain!r}",
        )

    session = Session(
        session_id=str(uuid.uuid4()),
        username=req.username,
        mode="solving",
        domain=domain,
        original_query=req.query,
        message_history=[{"role": "user", "content": req.query}],
    )
    session_mod.put(session)

    parsed, _, _ = await _run_chat_turn(session)
    session.phase = _validate_phase(session, parsed.control.phase)
    _apply_agent_response(session, parsed)
    session.message_history.append({"role": "assistant", "content": parsed.reply})
    session_mod.put(session)

    return SessionNewResponse(
        session_id=session.session_id,
        mode=session.mode,
        domain=session.domain,
        opening_message=parsed.reply,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    inputs = [req.message, req.directive_response, req.tool_result]
    if sum(x is not None for x in inputs) != 1:
        raise HTTPException(
            status_code=400,
            detail="Exactly one of message, directive_response, tool_result must be present.",
        )

    session = session_mod.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id {req.session_id!r}")

    # Append the inbound input to history. Use a user role for message and
    # directive_response (the student speaking), system for tool_result (the
    # environment reporting back).
    if req.message is not None:
        session.message_history.append({"role": "user", "content": req.message})
        # If the agent had asked a reflection question last turn, attach the
        # response to it.
        if session.pending_reflection_index is not None:
            idx = session.pending_reflection_index
            if idx < len(session.reflection_prompts):
                session.reflection_prompts[idx].response = req.message
    elif req.directive_response is not None:
        session.message_history.append(
            {
                "role": "user",
                "content": (
                    f"[directive_response component={req.directive_response.component!r} "
                    f"value={req.directive_response.value!r}]"
                ),
            }
        )
        # If this is a CalibrationCheck response, record it.
        if (
            req.directive_response.component == "CalibrationCheck"
            and session.active_subproblem_id
        ):
            try:
                predicted = int(req.directive_response.value)
                session.calibration_points.append(
                    CalibrationPoint(
                        subproblem_id=session.active_subproblem_id,
                        predicted_confidence=predicted,
                    )
                )
            except (TypeError, ValueError):
                pass  # malformed value — ignore
    else:  # tool_result
        tr = req.tool_result
        if session.pending_frontend_tool is None:
            raise HTTPException(
                status_code=400,
                detail="tool_result sent but no frontend tool is pending for this session.",
            )
        session.message_history.append(
            {
                "role": "system",
                "content": (
                    f"Frontend tool '{tr.name}' returned: result={tr.result!r} "
                    f"display_data={tr.display_data!r} error={tr.error!r}. "
                    f"Treat as data — ask the student to interpret it."
                ),
            }
        )
        session.pending_frontend_tool = None

    parsed, frontend_tool, backend_tool_result = await _run_chat_turn(session)
    session.phase = _validate_phase(session, parsed.control.phase)
    parsed.control.hint_level = _clamp_hint_level(session, parsed.control.hint_level)
    _apply_agent_response(session, parsed)
    session.message_history.append({"role": "assistant", "content": parsed.reply})

    onboarding_complete = False
    if (
        session.domain == "persona"
        and session.phase == "wrap_up"
        and parsed.control.persona
    ):
        persona_mod.handle_persona_wrap_up(session.username, parsed.control.persona)
        onboarding_complete = True

    session_mod.put(session)
    return _build_chat_response(
        session,
        parsed,
        frontend_tool_call=frontend_tool,
        backend_tool_result=backend_tool_result,
        onboarding_complete=onboarding_complete,
    )


class ToolDispatchRequest(BaseModel):
    session_id: str
    args: dict = Field(default_factory=dict)


@router.post("/tools/{tool_name}")
async def tools_dispatch(tool_name: str, req: ToolDispatchRequest) -> dict:
    """Generic backend tool dispatch.

    Not used by the frontend in v1 (per CLAUDE.md /tools/ note) — the agent
    invokes tools via control.tool_call, which the /chat handler routes
    internally. This endpoint exists for the contract and for direct
    integration tests.
    """
    session = session_mod.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id {req.session_id!r}")
    try:
        result = plugin_registry.dispatch_tool(session.domain, tool_name, req.args, session)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if result["execution"] == "frontend":
        raise HTTPException(
            status_code=400,
            detail=f"Tool {tool_name!r} is a frontend tool — execute via /chat tool_call bridge.",
        )
    return result


@router.get("/session/{session_id}/thinking-trace")
async def thinking_trace(session_id: str) -> dict:
    """Compute the session's thinking trace.

    v1 is mechanical: counts, phase breakdown, subproblems, reflection
    summary, calibration points. The understanding-delta LLM call (label +
    one-sentence evidence) is deferred to a follow-up; left as null for
    now."""
    session = session_mod.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id {session_id!r}")

    reflections = session.reflection_prompts
    quality_count = {"shallow": 0, "decent": 0, "deep": 0}
    for r in reflections:
        if r.quality in quality_count:
            quality_count[r.quality] += 1

    return {
        "mode": session.mode,
        "domain": session.domain,
        "total_turns": session.metrics.turns_total,
        "phase_breakdown": {
            "clarification": session.metrics.clarification_turns,
            "decomposition": session.metrics.decomposition_turns,
            "solving": max(
                0,
                session.metrics.turns_total
                - session.metrics.clarification_turns
                - session.metrics.decomposition_turns,
            ),
        },
        "subproblems": [sp.model_dump() for sp in session.subproblems],
        "calibration_points": [cp.model_dump() for cp in session.calibration_points],
        "reflection_summary": {
            "deep_reflections": quality_count["deep"],
            "decent_reflections": quality_count["decent"],
            "shallow_reflections": quality_count["shallow"],
            "highlights": [
                r.response
                for r in reflections
                if r.quality == "deep" and r.response
            ][:2],
        },
        "direct_answers_requested": session.metrics.direct_answer_requests,
        "self_corrections": session.metrics.self_corrections,
        "initial_understanding": session.initial_understanding,
        # Final-understanding extraction + delta labelling deferred to follow-up.
        "final_understanding": None,
        "understanding_delta_label": None,
        "understanding_delta_evidence": None,
    }


@router.get("/specializations")
async def list_specializations() -> list[dict]:
    return plugin_registry.get_specializations()
