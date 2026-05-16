# Calibration, Clarification, and Wrap-Up: Design vs. Implementation

## Section 1 — Intended Design

### Flow 1: Clarification phase

`phase_clarification.txt` instructs the agent to ask one problem-framing question and one understanding question, then exit to `decomposition` once the student articulates any initial understanding. CLAUDE.md says the frontend should render a contextual indicator when the phase is `clarification` — something like "First, let's make sure we understand the problem." The student's first substantive reply is stored as `session.initial_understanding`, which the thinking-trace endpoint uses at wrap-up to compute the understanding delta (initial vs. final articulation). The indicator clears when the phase changes.

### Flow 2: Calibration check

`block_calibration.txt` defines a predict-then-check loop: the agent emits `signal.emit_calibration_check: true` before a subproblem attempt; the backend converts this to a `CalibrationCheck` directive (question always backend-curated, never model-generated); the student selects 1–5; the backend stores the prediction as a `CalibrationPoint`; later the agent emits `signal.calibration_outcome` which is attached to that point. **XOR rule**: `emit_calibration_check: true` must not co-occur with a substantive `reply` — if both arrive, the backend strips `reply` so the student sees only the widget.

### Flow 3: Wrap-up reflection

`phase_wrap_up.txt` is explicit: "Session ends after reflection received, not when synthesis asked." Intended sequence: (turn N) agent enters `wrap_up`, emits `emit_reflection: "wrap_up"` + synthesis question; (turn N+1) student types reflection; (turn N+2) agent evaluates with `signal.last_reflection_quality` and closes warmly. The frontend must NOT transition to `WrapUpView` on the first `wrap_up` state event — only after the reflection round-trip is complete. **XOR rule**: when `emit_reflection` is set, `reply` should be null — the backend-selected reflection card is the student's prompt, not the model's chat text. `REFLECTION_QUESTIONS` must have ≥3 entries per trigger type with no in-session re-use.

---

## Section 2 — Current State (divergences from design)

### Flow 1: Clarification phase

`session.initial_understanding` is declared in `session.py:181` and read in `chat.py:1057` and `chat.py:1099` (thinking-trace endpoint and context string), but **nothing ever writes it**. `_finalize_turn` and `_apply_agent_response` contain no logic to capture the field on clarification→decomposition transitions. The thinking-trace summarizer receives `None` every session. On the frontend, `PhaseStepper` renders in the header but there is no contextual banner in the chat area — clarification looks identical to solving from the student's perspective.

### Flow 2: Calibration check

Steps 1–6 of the round-trip are fully implemented: directive injection (`chat.py:480–490`), component registration (`registry.ts:31`), `CalibrationCheck.tsx` component, directive-response handling (`chat.py:953–967`), outcome storage (`_apply_agent_response:381–385`), and thinking-trace output (`chat.py:1077`). **The XOR is missing.** `_build_chat_response` passes `parsed.reply` to `ChatResponse` unchanged even when `emit_calibration_check` is true. `_finalize_turn` has no code to set `parsed.reply = None` in this case.

### Flow 3: Wrap-up reflection

Three problems:

**(a) Frontend transitions too early.** `SessionView.tsx:102–104` calls `setTimeout(onWrapUp, 1800)` as soon as `res.phase === "wrap_up"` — the very turn the synthesis question appears. The student never gets to complete the reflection.

**(b) Reply not suppressed when emit_reflection is set.** `_build_chat_response` appends the `ReflectionPrompt` directive but still returns `parsed.reply`, so the student sees the model's chat text AND the reflection card — two different questions simultaneously.

**(c) REFLECTION_QUESTIONS bank is thin and not deduplicated.** `escape_hatch` has only 2 questions. All banks need expansion. `random.choice()` in `_apply_agent_response` makes no attempt to skip questions already asked this session.

---

## Section 3 — Plan (changes made in this commit)

### Backend — `backend/app/chat.py`

1. **Expand REFLECTION_QUESTIONS**: replaced the existing bank with the task-specified set (3–4 entries per trigger type, including a 3rd `escape_hatch` question).

2. **Add `wrap_up_complete` to `ChatResponse`**: new `bool` field. Set to `True` in `_finalize_turn` when `session.phase == "wrap_up"` AND `session.pending_reflection_index is None` after `_apply_agent_response` runs. This covers all cases: reflection quality evaluated (index cleared), wrap_up without reflection (index never set), reflection still pending (index set → False).

3. **Capture `initial_understanding`**: in `_finalize_turn`, before `_validate_phase` changes `session.phase`, detect a clarification→other transition and write the last plain user message to `session.initial_understanding` if not already set.

4. **XOR enforcement**: after the existing calibration/wrap_up phase guard, set `parsed.reply = None` if `emit_calibration_check` or `emit_reflection` is set. Applies to both JSON and SSE paths.

5. **Reflection question de-duplication**: filter `REFLECTION_QUESTIONS` bank against already-asked questions before `random.choice`; fall back to full bank if all exhausted.

### Frontend

6. **`types.ts`**: add `wrap_up_complete?: boolean` to `ChatResponse`.

7. **`SessionView.tsx` — transition guard**: replace `res.phase === "wrap_up"` with `res.wrap_up_complete === true`. The existing "End session →" button remains the manual escape hatch.

8. **`SessionView.tsx` — XOR streamed-text clear**: in `onState`, if any inline directive is `ReflectionPrompt` or `CalibrationCheck`, use `""` as fallback instead of pre-streamed content.

9. **`SessionView.tsx` — phase label banner**: thin contextual banner below the header for `clarification` ("First, let's make sure we understand the problem.") and `wrap_up` ("Let's look back at what you learned.") phases.

---

## Section 4 — Test Coverage

New tests in `backend/tests/test_clarification_calibration_wrapup.py`:

- `initial_understanding` is captured on clarification→decomposition transition; subsequent transitions do not overwrite it.
- `ChatResponse.reply` is `None` when `emit_calibration_check: true` (XOR).
- `ChatResponse.reply` is `None` when `emit_reflection` is set (XOR).
- `wrap_up_complete` is `False` when first entering wrap_up with a pending reflection.
- `wrap_up_complete` is `True` when quality evaluation arrives (reflection index cleared).
- `wrap_up_complete` is `True` when entering wrap_up without any reflection.
- Reflection question de-duplication skips already-asked questions.
