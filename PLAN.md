# Plan: Status After prompt-upgrade Milestone

## What Was Done

All P0–P4 + L1 + U1 + E1 items are complete. **121 fast tests pass.**

### Logging (L1) — Complete

| Event | File | Status |
|-------|------|--------|
| `llm_classifier` / `llm_classifier_error` | `llm.py call_classifier` | Done |
| `llm_summarizer` / `llm_summarizer_error` | `llm.py call_summarizer` | Done |
| `user_message_preview` in `llm_call` | `llm.py call_tutor` | Done |
| `chat_turn` in `chat.jsonl` | `chat.py /chat handler` | Done |

`call_classifier` now accepts `session_id: str = "classifier"`. Both `llm.jsonl` and `chat.jsonl` respect `LOG_LLM_CALLS=false`.

### Username-First UI (U1) — Complete

`OnboardingView` is now two steps:
- **Step 1**: username input → calls `POST /persona/create`
  - `status: "exists"` → advance to Step 2
  - `status: "confirm_new"` → inline "Start fresh?" prompt (new backend behaviour: `confirm: bool = False` prevents accidental account creation)
  - `status: "pending"` → route to persona intake session
- **Step 2**: problem textarea → calls `POST /session/new`
- "← Not {name}?" resets to Step 1

`App.tsx` `persona_session` route no longer holds `pendingQuery`. After persona intake completes (`onboarding_complete: true`), routes to `{ kind: "onboarding", initialStep: "query", initialUsername }`.

### Wrap-Up / Thinking Trace (E1) — Partially Complete

`ThinkingTraceDrawer` now renders:
- **Calibration section** — predicted confidence vs. outcome per subproblem
- **Reflections section** — question / answer / quality badge per reflection

`ThinkingTrace` in `types.ts` gains `reflection_prompts` and `calibration_points`.

**Known gap:** These sections are empty in real sessions. The agent rarely emits `emit_calibration_check` or `emit_reflection` signals because the prompt does not make the trigger conditions concrete enough. See "Next work" below.

### Session Context (P0–P4) — Complete

`session.to_context_str()` now includes:
- Per subproblem: `goal`, `hints_given`, `direct_answer_requested`
- Session level: `self_corrections`, `turns_total`

This gives the agent the pacing data it needs to decide when to escalate, reflect, or calibrate.

---

## Known Issues (not fixed this milestone)

### Wrap-Up / Reflection Not Triggering

**Root cause:** The prompt does not tell the agent *when* to emit `emit_reflection` or `emit_calibration_check` concretely enough. The signal names appear in the schema docs but are not linked to specific session state thresholds the agent can observe (e.g. "emit calibration check before the student's first attempt at each subproblem").

**Symptoms:**
- `reflection_prompts` array is always empty at wrap-up
- `calibration_points` array is always empty at wrap-up
- ThinkingTraceDrawer Calibration and Reflections sections never show content

**Fix needed:** In `backend/app/prompts/socratic_base.txt`, add explicit trigger rules:
- `emit_calibration_check: true` — emit on the turn that activates a new subproblem (i.e. when `active_subproblem` just changed and it's the first hint at level 0)
- `emit_reflection: "periodic"` — emit every 2 solved subproblems (check `turns_total % 6 == 0` as a proxy, or count solved subproblems)
- `emit_reflection: "self_correction"` — emit the turn after `self_correction_noted: true` is observed
- `emit_reflection: "escape_hatch"` — emit immediately before showing the answer (same turn as `escape_hatch_triggered: true`)
- `emit_reflection: "wrap_up"` — emit on the wrap_up turn

Also add to the prompt: the condition "if `emit_calibration_check` was emitted this turn, do NOT set phase to `wrap_up`" (already enforced by backend but the agent doesn't know why it gets clamped).

### Prompt Fine-Tuning Still Needed

The domain prompts and socratic_base have been expanded but real sessions still show:
- Agent occasionally gives direct answers when hint_level > 3 (should offer escape hatch first)
- Agent sometimes asks two questions in one turn despite the one-question rule
- `decomposition_source` is rarely set (agent doesn't track whether the student or tutor proposed each subproblem)
- `refined_query` is rarely populated after clarification phase

These are tracked in `PROMPT_ISSUES.md`.

---

## Next Work (in order)

### 1. Fix wrap-up signal emission (prompt tuning)

**Files:** `backend/app/prompts/socratic_base.txt`

Add a "Signal emission guide" section with concrete trigger rules (see above). Run the `emit_calibration_check` and `emit_reflection` probes after the change to verify.

**Verification:**
```bash
cd backend && python -m tests.run_probes --probe emit_calibration_check
cd backend && python -m tests.run_probes --probe emit_reflection_periodic
```
Manual check: start a real session, solve one subproblem, confirm ThinkingTraceDrawer shows calibration and reflection data at wrap-up.

### 2. SSE streaming

`backend/app/llm.py` — implement `stream_tutor()`:
- Call OpenRouter with `stream=True`
- Yield `("token", delta)` for content chunks
- Accumulate full response, parse JSON, yield `("state", control_obj)` at end
- On parse failure: retry once in non-streaming mode

Frontend `ChatPane` needs to consume `token` events to show streaming text and `state` event to update session state.

### 3. Seeded dialogue tests

Add at least 3 seeded dialogues to `tests/test_socratic_constraints.py`:
- Each is a list of `(user_message, canned_llm_reply)` pairs
- Assert after each turn: `no_solution_leak`, `one_question`, `no_enumeration`
- Cover: math (algebra), programming (pseudocode ask), essay (no drafted paragraph)

### 4. Deploy to EC2

nginx + systemd + Let's Encrypt. See CLAUDE.md "Deployment" section.

---

## Future Widget Plans (F1 — no implementation)

### F1.1 — File attachment widget

**UX (Step 2 of OnboardingView):** "📎 Attach file" button → native file picker (`.pdf`, `.png`, `.jpg`, `.py`, `.js`, `.txt`). Selected filename shown as chip with ✕. One file max.

**Frontend wiring:**
- `AttachmentChip` component (display + remove)
- `OnboardingView` Step 2: `attachmentFile: File | null` state
- On submit: read as text (`FileReader.readAsText`) or extract PDF via `pdf.js`; prepend `"[File: {name}]\n{contents}\n\n"` to query
- Files > 2 MB rejected inline; no server upload

**Multimodality note:** For image files (`.png`, `.jpg`), send the image directly to a vision-capable model. `gemini-2.5-flash` supports image input via OpenRouter's multimodal content array `{ type: "image_url", image_url: { url: "data:image/png;base64,..." } }`. The backend's `build_prompt` would need to accept an `attachment` field and splice it into the last user message as a multimodal content block — only if the active model supports vision.

**Files (when implementing):** `frontend/src/components/AttachmentChip.tsx`, `frontend/src/utils/extractFileText.ts`, `OnboardingView.tsx` Step 2 additions, `backend/app/chat.py` `build_prompt` multimodal splice.

### F1.2 — Subject/domain hint widget

**UX (Step 2):** Pill row above textarea — `[Math] [Programming] [Essay] [Science] [Not sure]`. Default is `Not sure`.

**Frontend:** `DomainPillRow` component; `domainHint: string | null` state; pass `domain_hint` to `api.sessionNew`.

**Backend:** `SessionNew` gains `domain_hint: str | None = None`. If provided and valid, skip `call_classifier`. Log `domain_hint_used` event to `chat.jsonl`.

**Files (when implementing):** `frontend/src/components/DomainPillRow.tsx`, `frontend/src/api/types.ts` (add `domain_hint?`), `backend/app/chat.py` (SessionNew + classifier bypass).
