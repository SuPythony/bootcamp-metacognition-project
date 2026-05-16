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

import datetime
import json
import logging
import os
import random
import sys
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

_log = logging.getLogger("app.chat")


# ---------------------------------------------------------------------------
# Chat-turn JSONL logger (separate from llm.jsonl)
# ---------------------------------------------------------------------------

def _setup_chat_logger() -> logging.Logger:
    logger = logging.getLogger("chat.turns")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter("%(message)s")
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    fh = logging.FileHandler(logs_dir / "chat.jsonl", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def _write_chat_log(entry: dict) -> None:
    if os.environ.get("LOG_LLM_CALLS", "true").lower() in ("false", "0", "no"):
        return
    try:
        _setup_chat_logger().debug(json.dumps(entry))
        llm._write_log(entry)  # mirror into llm.jsonl so view_logs.py sees everything
    except Exception:
        pass

from app import llm, persona as persona_mod, plugin_registry
from app import session as session_mod
from app.prompts.variants import load_base_prompt, load_prompt, parse_domain_variants
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

# ---------------------------------------------------------------------------
# Startup-time configuration — read once, applies to ALL sessions this run.
# ---------------------------------------------------------------------------

# LLM temperatures. Defaults: 0.7 for tutor (creative), 0.0 for classifier (deterministic).
_TUTOR_TEMP: float = float(os.environ.get("TUTOR_TEMPERATURE", "0.7"))
_CLASSIFIER_TEMP: float = float(os.environ.get("CLASSIFIER_TEMPERATURE", "0.0"))

# Prompt variant selection. All sessions in this server process use the same variant.
# PROMPT_VARIANT_BASE: single key e.g. "base:v2"
# PROMPT_VARIANT_DOMAIN: comma-separated "<domain>:<version>" pairs e.g. "math:v2,essay:v1"
_VARIANT_BASE: str | None = os.environ.get("PROMPT_VARIANT_BASE")
_VARIANT_DOMAIN_MAP: dict[str, str] = parse_domain_variants(
    os.environ.get("PROMPT_VARIANT_DOMAIN", "")
)


# ---- Reflection question banks ----------------------------------------------
# Backend selects the question; the model emits only the trigger type.

REFLECTION_QUESTIONS: dict[str, list[str]] = {
    "periodic": [
        "What was different about how you approached this part compared to the last one?",
        "Is there anything about your thinking on that step that surprised you?",
        "If you had to do that step again from scratch, what would you do differently?",
    ],
    "self_correction": [
        "What made you change your mind just then?",
        "How did you notice the mistake — what tipped you off?",
        "What does catching that tell you about how you're thinking through this?",
    ],
    "escape_hatch": [
        "Before I show you — in one sentence, where exactly did your thinking get stuck?",
        "Just one sentence: what was the specific moment you felt you hit a wall?",
    ],
    "wrap_up": [
        "Can you walk me through the full solution in your own words — start to finish?",
        "If you were explaining this to a friend, what would you say was the key insight?",
        "What would you tell someone who's about to tackle this same problem?",
    ],
}


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
    """Navigation fields the backend validates every turn.

    Fields that moved to `signal` in the new schema are kept here with None
    defaults for backward-compat during the migration. Handlers no longer read
    them — they log a debug warning if non-None so we can confirm the model
    stopped emitting them after the prompt change.
    """

    phase: Phase | None = None
    active_subproblem: str | None = None
    hint_level: int | None = None  # null = no-op; integer = new escalation level
    tool_call: dict | None = None
    ui_directives: list[dict] = Field(default_factory=list)
    # --- deprecated fields (moved to signal) — kept for backward-compat only ---
    subproblem_updates: list[dict] = Field(default_factory=list)
    reflection_prompt: dict | None = None   # replaced by signal.emit_reflection
    last_reflection_quality: Literal["shallow", "decent", "deep"] | None = None
    calibration_check: str | None = None    # replaced by signal.emit_calibration_check
    calibration_outcome: Literal["correct", "wrong", "partial"] | None = None
    persona_updates: list[dict] = Field(default_factory=list)
    self_correction_noted: bool = False
    escape_hatch_triggered: bool = False
    escape_hatch_reflection: str | None = None
    # Persona onboarding wrap_up: the stub persona payload to write to disk.
    persona: dict | None = None


class AgentSignal(BaseModel):
    """Optional session-event block. Absent entirely on quiet turns."""

    subproblem_updates: list[dict] = Field(default_factory=list)
    emit_reflection: Literal["periodic", "self_correction", "escape_hatch", "wrap_up"] | None = None
    last_reflection_quality: Literal["shallow", "decent", "deep"] | None = None
    emit_calibration_check: bool = False
    calibration_outcome: Literal["correct", "wrong", "partial"] | None = None
    persona_updates: list[dict] = Field(default_factory=list)
    self_correction_noted: bool = False
    escape_hatch_triggered: bool = False
    escape_hatch_reflection: str | None = None
    verification_prompted: bool = False
    concepts_established: list[str] = Field(default_factory=list)
    student_question_quality: Literal["surface", "probing", "insightful"] | None = None
    decomposition_source: Literal["student", "tutor"] | None = None
    disengagement_noted: bool = False
    refined_query: str | None = None


class AgentResponse(BaseModel):
    thinking: str | None = None   # scratchpad — stripped before any downstream use
    reply: str | None = None      # null when tool_call is set
    control: AgentControl = Field(default_factory=AgentControl)
    signal: AgentSignal | None = None


class ChatResponse(BaseModel):
    reply: str | None
    phase: Phase
    domain: str
    subproblems: list[Subproblem]
    active_subproblem: str | None
    ui_directives: list[dict]
    frontend_tool_call: dict | None = None
    # Backend tool results from this turn, ready for the ToolPane to render.
    # Shaped as ToolCall: { name, ui_component, display_data, ... }
    tool_calls: list[dict] = Field(default_factory=list)
    onboarding_complete: bool = False


# ---- Helpers ----------------------------------------------------------------


_MAX_TOOL_ITERATIONS = 3


def _build_messages(
    session: Session, persona_ctx: str, had_tool_result: bool = False
) -> list[dict]:
    """Build the OpenAI-style message list for an LLM call."""
    base_text = load_base_prompt(
        variant_key=_VARIANT_BASE,
        session=session,
        had_tool_result=had_tool_result,
    )
    domain_text = load_prompt(
        session.domain,
        variant_key=_VARIANT_DOMAIN_MAP.get(session.domain),
    )
    system_content = base_text + "\n\n" + domain_text
    return [
        {"role": "system", "content": system_content},
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


def _clamp_hint_level(session: Session, proposed: int | None) -> int | None:
    """Clamp escalation to +1 over the active subproblem's current level.
    None means no hint this turn — pass through unchanged."""
    if proposed is None:
        return None
    if proposed <= 0:
        return None  # treat non-positive as no-op same as null
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
    """Mutate the session in-place to reflect the agent's emitted control/signal.
    Phase must be validated and applied by the caller BEFORE this is called;
    this function skips the phase field intentionally to avoid overwriting the
    validated phase with the raw (potentially clamped) value."""
    control = parsed.control
    signal = parsed.signal  # may be None on quiet turns

    # ---- control fields (navigation, always present) -------------------------

    # Active subproblem activation (from control, still lives there).
    if control.active_subproblem is not None:
        session.active_subproblem_id = control.active_subproblem
        for sp in session.subproblems:
            if sp.id == control.active_subproblem and sp.status == "pending":
                sp.status = "active"

    # Hint level: null = no-op (do not overwrite).
    if control.hint_level is not None:
        sp = session.active_subproblem()
        if sp is not None:
            sp.hints_given = control.hint_level
            session.metrics.hints_per_subproblem[sp.id] = sp.hints_given

    # ---- signal fields (session events, optional block) ----------------------

    if signal is not None:
        # Subproblem updates (moved from control to signal).
        if signal.subproblem_updates:
            _apply_subproblem_updates(session, signal.subproblem_updates)
            # Warn if any subproblem closed without verification being prompted.
            for upd in signal.subproblem_updates:
                if upd.get("status") == "solved":
                    sp_id = upd.get("id")
                    if sp_id and sp_id not in session.verification_prompted_subproblems:
                        _log.warning(
                            "session=%s subproblem %r closed as solved without "
                            "verification_prompted being set this session",
                            session.session_id[:8], sp_id,
                        )

        # Verification prompted — record against active subproblem.
        if signal.verification_prompted and session.active_subproblem_id:
            if session.active_subproblem_id not in session.verification_prompted_subproblems:
                session.verification_prompted_subproblems.append(session.active_subproblem_id)

        # Reflection trigger — queue and remember index for next-turn quality attach.
        emit_trigger = signal.emit_reflection
        if emit_trigger:
            question = random.choice(
                REFLECTION_QUESTIONS.get(emit_trigger, REFLECTION_QUESTIONS["periodic"])
            )
            rp = ReflectionPrompt(trigger=emit_trigger, question=question)
            session.reflection_prompts.append(rp)
            session.pending_reflection_index = len(session.reflection_prompts) - 1

        # Reflection quality attaches to the previous pending reflection.
        if signal.last_reflection_quality and session.reflection_prompts:
            idx = session.pending_reflection_index
            if idx is not None and idx < len(session.reflection_prompts):
                session.reflection_prompts[idx].quality = signal.last_reflection_quality
            else:
                # Quality arrived without a pending index (e.g. agent evaluated two turns late).
                # Walk back to attach to the most recent un-evaluated reflection.
                for rp in reversed(session.reflection_prompts):
                    if rp.quality is None:
                        rp.quality = signal.last_reflection_quality
                        break
                else:
                    _log.warning(
                        "last_reflection_quality=%r arrived but no pending reflection found; discarded",
                        signal.last_reflection_quality,
                    )
            session.pending_reflection_index = None

        # Calibration outcome attaches to the most recent open calibration point.
        if signal.calibration_outcome and session.active_subproblem_id:
            for cp in reversed(session.calibration_points):
                if cp.subproblem_id == session.active_subproblem_id and cp.outcome is None:
                    cp.outcome = signal.calibration_outcome
                    break

        # Persona updates.
        if signal.persona_updates:
            persona_mod.merge_persona_updates(session.username, signal.persona_updates)

        # Self-correction.
        if signal.self_correction_noted:
            session.metrics.self_corrections += 1

        # Escape hatch.
        if signal.escape_hatch_triggered:
            sp = session.active_subproblem()
            if sp is not None:
                sp.direct_answer_requested = True
                if signal.escape_hatch_reflection:
                    sp.escape_hatch_reflection = signal.escape_hatch_reflection
            session.metrics.direct_answer_requests += 1

        # Concepts established — extend session list (prevents re-asking).
        if signal.concepts_established:
            for concept in signal.concepts_established:
                if concept not in session.concepts_established:
                    session.concepts_established.append(concept)

        # Student question quality — per-turn analytics.
        if signal.student_question_quality:
            session.student_questions.append({"quality": signal.student_question_quality})

        # Decomposition source — record first assignment only.
        if signal.decomposition_source and session.decomposition_source is None:
            session.decomposition_source = signal.decomposition_source

        # Disengagement counter.
        if signal.disengagement_noted:
            session.disengagement_count += 1

        # Refined query — overwrite on each set (latest clarification wins).
        if signal.refined_query:
            session.refined_query = signal.refined_query

    # ---- Phase-counter metrics (always) --------------------------------------
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
    directives = list(parsed.control.ui_directives)

    # Auto-inject ReflectionPrompt widget when signal.emit_reflection is set.
    # Question is selected from the backend bank — not generated by the model.
    if parsed.control.reflection_prompt:
        _log.debug(
            "deprecated: control.reflection_prompt is set (%r) — "
            "model should emit signal.emit_reflection instead",
            parsed.control.reflection_prompt,
        )
    emit_trigger = parsed.signal.emit_reflection if parsed.signal else None
    if emit_trigger and not any(d.get("component") == "ReflectionPrompt" for d in directives):
        # Reuse the question already chosen and stored in _apply_agent_response so
        # the directive and the session record are consistent.
        idx = session.pending_reflection_index
        if idx is not None and 0 <= idx < len(session.reflection_prompts):
            question = session.reflection_prompts[idx].question
        else:
            question = random.choice(REFLECTION_QUESTIONS.get(emit_trigger, REFLECTION_QUESTIONS["periodic"]))
        directives.append({
            "component": "ReflectionPrompt",
            "domain": "general",
            "props": {
                "question": question,
                "trigger": emit_trigger,
            },
            "placement": "inline",
            "lifetime": "until_next_turn",
        })

    # Auto-inject CalibrationCheck widget when signal.emit_calibration_check is true.
    # Widget question is backend-defined (not model-generated).
    if parsed.control.calibration_check:
        _log.debug(
            "session deprecated: control.calibration_check is set (%r) — "
            "model should emit signal.emit_calibration_check instead",
            parsed.control.calibration_check,
        )
    cc = parsed.signal is not None and parsed.signal.emit_calibration_check
    if cc and not any(d.get("component") == "CalibrationCheck" for d in directives):
        directives.append({
            "component": "CalibrationCheck",
            "domain": "general",
            "props": {
                "question": "Before you try — how confident are you that you'll get this right? 1 to 5.",
            },
            "placement": "inline",
            "lifetime": "until_next_turn",
        })

    return ChatResponse(
        reply=parsed.reply,
        phase=session.phase,
        domain=session.domain,
        subproblems=session.subproblems,
        active_subproblem=session.active_subproblem_id,
        ui_directives=directives,
        frontend_tool_call=frontend_tool_call,
        tool_calls=[backend_tool_result] if backend_tool_result else [],
        onboarding_complete=onboarding_complete,
    )


async def _run_chat_turn(
    session: Session, had_tool_result: bool = False
) -> tuple[AgentResponse, dict | None, dict | None]:
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

    messages = _build_messages(session, persona_ctx, had_tool_result=had_tool_result)
    last_backend_tool_result: dict | None = None
    last_tool_name: str | None = None  # tracks last executed tool for dedup

    for iteration in range(_MAX_TOOL_ITERATIONS):
        raw, usage = await llm.call_tutor(messages, session_id=session.session_id, temperature=_TUTOR_TEMP)
        session.metrics.token_usage.add(usage)
        _log.info(
            "tokens iter=%d session=%s prompt=%d completion=%d | session_total=%d",
            iteration,
            session.session_id[:8],
            usage["prompt_tokens"],
            usage["completion_tokens"],
            session.metrics.token_usage.total_tokens,
        )
        # Strip `thinking` before parsing — it must never reach the frontend.
        raw.pop("thinking", None)
        try:
            parsed = AgentResponse.model_validate(raw)
            llm.mark_parse_result(session.session_id, True)
        except Exception as e:  # pydantic.ValidationError or similar
            llm.mark_parse_result(session.session_id, False, str(e))
            raise HTTPException(
                status_code=502,
                detail=f"Agent output failed schema validation: {e}",
            ) from e
        parsed.thinking = None  # belt-and-suspenders: ensure field is never forwarded

        # Enforce tool_call / reply mutual exclusion.
        # If the agent wrote a multi-sentence reply alongside a tool_call, the
        # student would see the answer before interpreting tool output — defeats
        # constraint 4. Retry once with a corrective note.
        if parsed.control.tool_call is not None and parsed.reply:
            word_count = len(parsed.reply.split())
            # Count sentence-ending punctuation as a proxy for multiple sentences.
            sentence_count = sum(parsed.reply.count(p) for p in ".?!")
            if word_count > 30 or sentence_count > 1:
                _log.warning(
                    "session=%s tool_call set but reply is too long (%d words, %d sentences) — retrying",
                    session.session_id[:8], word_count, sentence_count,
                )
                correction_messages = messages + [
                    {"role": "assistant", "content": str(raw)},
                    {
                        "role": "system",
                        "content": (
                            "You emitted tool_call with a multi-sentence reply. "
                            "When tool_call is set, reply must be null or one short "
                            "framing sentence only (≤30 words). Rewrite."
                        ),
                    },
                ]
                raw2, usage2 = await llm.call_tutor(
                    correction_messages,
                    session_id=session.session_id,
                    temperature=_TUTOR_TEMP,
                )
                session.metrics.token_usage.add(usage2)
                raw2.pop("thinking", None)
                try:
                    parsed = AgentResponse.model_validate(raw2)
                    parsed.thinking = None
                except Exception:
                    _log.warning(
                        "session=%s tool_call/reply retry failed to parse — using original",
                        session.session_id[:8],
                    )

        if parsed.control.tool_call is None:
            return parsed, None, last_backend_tool_result

        tool_name = parsed.control.tool_call.get("name")
        tool_args = parsed.control.tool_call.get("args", {})
        if not tool_name:
            raise HTTPException(
                status_code=502, detail="Agent emitted tool_call without 'name'"
            )

        # Guard: if the model calls the same tool again after already receiving
        # its result, return early rather than executing and looping.
        if tool_name == last_tool_name and last_backend_tool_result is not None:
            _log.warning(
                "session=%s tool=%r called again after result already returned — "
                "breaking loop and returning existing result",
                session.session_id[:8],
                tool_name,
            )
            return parsed, None, last_backend_tool_result

        try:
            dispatch = plugin_registry.dispatch_tool(
                session.domain, tool_name, tool_args, session
            )
        except KeyError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        if dispatch["execution"] == "frontend":
            session.pending_frontend_tool = dispatch
            return parsed, dispatch, last_backend_tool_result

        # Always record the assistant turn that issued the call so the next
        # LLM iteration sees a coherent [user → assistant → system] thread.
        # Skipping this when reply is empty was the original bug: the model
        # saw a tool result with no prior assistant message and re-issued the
        # same call every iteration.
        assistant_msg = {"role": "assistant", "content": parsed.reply or ""}
        messages.append(assistant_msg)
        session.message_history.append(assistant_msg)

        last_tool_name = tool_name
        last_backend_tool_result = dispatch
        display_data = dispatch.get("display_data", {})
        tool_msg = {
            "role": "user",
            "content": (
                f"[SYSTEM] Tool '{tool_name}' result:\n"
                f"  answer: {dispatch.get('result')!r}\n"
                f"  display (shown to student): {json.dumps(display_data)}\n"
                f"Reply to the student now. Ask them to interpret this output. "
                f"Do not call any tool. Set tool_call to null."
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
        classifier_output, cls_usage = await llm.call_classifier(req.query, temperature=_CLASSIFIER_TEMP)
    except llm.LLMClassifierError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    _log.info(
        "classifier tokens prompt=%d completion=%d domain=%s",
        cls_usage["prompt_tokens"],
        cls_usage["completion_tokens"],
        classifier_output.get("domain"),
    )
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
    session.metrics.token_usage.add(cls_usage)  # count classifier call in session total

    parsed, _, _ = await _run_chat_turn(session)
    previous_phase = session.phase
    session.phase = _validate_phase(session, parsed.control.phase)
    _apply_agent_response(session, parsed)
    session.message_history.append({"role": "assistant", "content": parsed.reply or ""})
    await _maybe_capture_initial_understanding(session, previous_phase)
    session_mod.put(session)

    return SessionNewResponse(
        session_id=session.session_id,
        mode=session.mode,
        domain=session.domain,
        opening_message=parsed.reply,
    )


async def _maybe_capture_initial_understanding(
    session: Session, previous_phase: Phase
) -> None:
    """If the session has just left clarification for the first time, synthesise
    initial_understanding from its clarification-phase student messages.

    Idempotent: a non-None initial_understanding is never overwritten, so
    re-entries (phase clamps, replays) don't trigger a second call.
    """
    if session.initial_understanding is not None:
        return
    if previous_phase != "clarification" or session.phase == "clarification":
        return
    clarification_msgs = [
        m["content"]
        for m in session.message_history
        if m.get("role") == "user" and not m["content"].startswith("[SYSTEM]")
    ]
    if not clarification_msgs:
        return
    summary = await llm.call_initial_understanding_summarizer(
        clarification_student_messages=clarification_msgs,
        session_id=session.session_id,
    )
    if summary:
        session.initial_understanding = summary


async def _finalize_turn(
    session: Session,
    req: ChatRequest,
    parsed: AgentResponse,
    frontend_tool: dict | None,
    backend_tool_result: dict | None,
) -> ChatResponse:
    """Apply phase/signal/persona logic after the LLM call(s) complete and build
    the ChatResponse.  Called by both the JSON path and the SSE generator so the
    logic lives in exactly one place.
    """
    calibration_requested = (
        (parsed.signal is not None and parsed.signal.emit_calibration_check)
        or bool(parsed.control.calibration_check)
    )
    if calibration_requested and parsed.control.phase == "wrap_up":
        _log.warning(
            "session=%s blocked wrap_up phase transition on same turn as calibration_check",
            req.session_id[:8],
        )
        parsed.control.phase = None

    previous_phase = session.phase
    session.phase = _validate_phase(session, parsed.control.phase)
    parsed.control.hint_level = _clamp_hint_level(session, parsed.control.hint_level)
    _apply_agent_response(session, parsed)
    session.message_history.append({"role": "assistant", "content": parsed.reply or ""})

    await _maybe_capture_initial_understanding(session, previous_phase)

    onboarding_complete = False
    if session.domain == "persona" and session.phase == "wrap_up":
        persona_payload: dict = {}
        if parsed.signal and parsed.signal.persona_updates:
            for upd in parsed.signal.persona_updates:
                if upd.get("operation") == "set" and upd.get("field") and upd.get("value") is not None:
                    persona_payload[upd["field"]] = upd["value"]
        if not persona_payload and parsed.control.persona:
            persona_payload = parsed.control.persona
        persona_mod.handle_persona_wrap_up(
            session.username, persona_payload, session_id=session.session_id
        )
        onboarding_complete = True

    _write_chat_log({
        "event": "chat_turn",
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": req.session_id,
        "turn": session.metrics.turns_total,
        "phase": session.phase,
        "active_subproblem": session.active_subproblem_id,
        "hint_level": session.current_hint_level(),
        "input_kind": (
            "message" if req.message is not None
            else "directive_response" if req.directive_response is not None
            else "tool_result"
        ),
        "user_message": req.message,
        "agent_reply_preview": (parsed.reply or "")[:120],
        "tool_called": (parsed.control.tool_call.get("name") if isinstance(parsed.control.tool_call, dict) else None),
        "phase_after": session.phase,
    })
    session_mod.put(session)
    return _build_chat_response(
        session, parsed,
        frontend_tool_call=frontend_tool,
        backend_tool_result=backend_tool_result,
        onboarding_complete=onboarding_complete,
    )


async def _chat_sse_generator(
    req: ChatRequest,
    session: Session,
    had_tool_result: bool,
) -> AsyncGenerator[str, None]:
    """Async generator for the SSE path.  Yields SSE-formatted strings.

    First LLM call uses stream_tutor() so reply tokens are emitted in real time.
    Backend tool-call follow-ups use call_tutor() (non-streaming) then emit the
    second reply tokens via a second stream_tutor() call.
    Final `state` event carries the full ChatResponse JSON.
    """

    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        persona = persona_mod.load_persona(session.username)
        persona_ctx = persona.to_context_str() if persona else "No persona on file yet."
        messages = _build_messages(session, persona_ctx, had_tool_result=had_tool_result)
        last_backend_tool_result: dict | None = None
        last_tool_name: str | None = None

        for iteration in range(_MAX_TOOL_ITERATIONS):
            # Stream the LLM call — emit token events as reply chars arrive.
            full_raw: dict | None = None
            stream_error: str | None = None
            async for etype, edata in llm.stream_tutor(
                messages, session_id=session.session_id, temperature=_TUTOR_TEMP
            ):
                if etype == "token":
                    yield _sse("token", {"delta": edata})
                elif etype == "state":
                    full_raw = edata
                elif etype == "error":
                    stream_error = edata
                    break  # exit inner loop; fall through to non-streaming retry

            if full_raw is None:
                if stream_error is not None:
                    # Streaming parse failed (usually truncated JSON at token limit).
                    # Retry once with non-streaming call_tutor so the user never sees
                    # the error. Any partial tokens already sent will be overwritten
                    # when the state event arrives with the full reply.
                    _log.warning(
                        "session=%s SSE streaming parse failed, retrying non-streaming: %s",
                        session.session_id[:8], stream_error[:120],
                    )
                    try:
                        raw_dict, _ = await llm.call_tutor(
                            messages, session_id=session.session_id, temperature=_TUTOR_TEMP
                        )
                        full_raw = raw_dict
                    except Exception as retry_exc:
                        yield _sse("error", {"message": f"Streaming failed and retry failed: {retry_exc}"})
                        return
                else:
                    yield _sse("error", {"message": "No response received from model"})
                    return

            full_raw.pop("thinking", None)
            try:
                parsed = AgentResponse.model_validate(full_raw)
                llm.mark_parse_result(session.session_id, True)
            except Exception as e:
                llm.mark_parse_result(session.session_id, False, str(e))
                yield _sse("error", {"message": f"Agent output failed schema validation: {e}"})
                return
            parsed.thinking = None

            # Tool/reply mutual exclusion (same guard as JSON path).
            if parsed.control.tool_call is not None and parsed.reply:
                word_count = len(parsed.reply.split())
                sentence_count = sum(parsed.reply.count(p) for p in ".?!")
                if word_count > 30 or sentence_count > 1:
                    _log.warning(
                        "session=%s (sse) tool_call set but reply too long — discarding reply",
                        session.session_id[:8],
                    )
                    parsed.reply = None

            if parsed.control.tool_call is None:
                break

            tool_name = parsed.control.tool_call.get("name")
            tool_args = parsed.control.tool_call.get("args", {})
            if not tool_name:
                yield _sse("error", {"message": "Agent emitted tool_call without 'name'"})
                return

            if tool_name == last_tool_name and last_backend_tool_result is not None:
                _log.warning("session=%s (sse) duplicate tool call — breaking loop", session.session_id[:8])
                break

            try:
                dispatch = plugin_registry.dispatch_tool(session.domain, tool_name, tool_args, session)
            except KeyError as e:
                yield _sse("error", {"message": str(e)})
                return

            if dispatch["execution"] == "frontend":
                session.pending_frontend_tool = dispatch
                # Surface to client via state event below; no more LLM calls needed.
                break

            assistant_msg = {"role": "assistant", "content": parsed.reply or ""}
            messages.append(assistant_msg)
            session.message_history.append(assistant_msg)

            last_tool_name = tool_name
            last_backend_tool_result = dispatch
            display_data = dispatch.get("display_data", {})
            tool_msg = {
                "role": "user",
                "content": (
                    f"[SYSTEM] Tool '{tool_name}' result:\n"
                    f"  answer: {dispatch.get('result')!r}\n"
                    f"  display (shown to student): {json.dumps(display_data)}\n"
                    f"Reply to the student now. Ask them to interpret this output. "
                    f"Do not call any tool. Set tool_call to null."
                ),
            }
            messages.append(tool_msg)
            session.message_history.append(tool_msg)
            # Loop: next iteration streams the post-tool reply.

        frontend_tool = session.pending_frontend_tool if hasattr(session, "pending_frontend_tool") and session.pending_frontend_tool else None

        chat_response = await _finalize_turn(session, req, parsed, frontend_tool, last_backend_tool_result)
        yield _sse("state", chat_response.model_dump())

    except HTTPException as exc:
        yield _sse("error", {"code": exc.status_code, "message": exc.detail})
    except Exception as exc:
        _log.exception("Unhandled error in SSE generator session=%s", req.session_id[:8])
        yield _sse("error", {"code": 500, "message": str(exc)})


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
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

    had_tool_result = req.tool_result is not None

    # SSE path: stream reply tokens in real time, emit `state` event at end.
    if "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(
            _chat_sse_generator(req, session, had_tool_result),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # JSON path (backward-compat, used by tests and non-streaming clients).
    parsed, frontend_tool, backend_tool_result = await _run_chat_turn(
        session, had_tool_result=had_tool_result
    )
    return await _finalize_turn(session, req, parsed, frontend_tool, backend_tool_result)


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

    Fires a cheap LLM call to synthesise final_understanding and the
    understanding delta from the student's recent messages."""
    session = session_mod.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id {session_id!r}")

    reflections = session.reflection_prompts
    quality_count = {"shallow": 0, "decent": 0, "deep": 0}
    for r in reflections:
        if r.quality in quality_count:
            quality_count[r.quality] += 1

    # Extract recent student messages for the summariser.
    recent_student = [
        m["content"]
        for m in session.message_history
        if m.get("role") == "user" and not m["content"].startswith("[SYSTEM]")
    ]

    summary = await llm.call_summarizer(
        initial_understanding=session.initial_understanding,
        recent_student_messages=recent_student,
        session_id=session_id,
    )

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
        "reflection_prompts": [
            {
                "trigger": r.trigger,
                "question": r.question,
                "response": r.response,
                "quality": r.quality,
            }
            for r in reflections
        ],
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
        "refined_query": session.refined_query,
        "concepts_established": session.concepts_established,
        "decomposition_source": session.decomposition_source,
        "disengagement_count": session.disengagement_count,
        "final_understanding": summary["final_understanding"],
        "understanding_delta_label": summary["delta_label"],
        "understanding_delta_evidence": summary["delta_evidence"],
    }


@router.get("/specializations")
async def list_specializations() -> list[dict]:
    return plugin_registry.get_specializations()
