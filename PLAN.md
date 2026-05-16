# Aporeka — Development Plan

Consolidated action plan drawing from `ISSUES.md` (engineering issues) and `PROMPT_ISSUES.md`
(prompt-only issues). Items are ordered by priority tier. Prompt-only changes are called out
separately — they require no code and can run in parallel with any engineering work.

---

## Priority 1 — Fix before demo

Low effort, high visibility. These should land before any public showing.

### 1a. Wrap-up reflection: fix fragility + fill question bank
**From:** ISSUES.md #1 | **Effort:** Low | **Owner:** Backend + Frontend

The session can close before the student responds to the wrap-up reflection card — the SSE
connection drops or the frontend transitions state before the card renders.

- **Frontend:** Hold the session open (keep SSE connection alive) until
  `signal.last_reflection_quality` has been received and stored. Do not transition to
  `WrapUpView` until this arrives.
- **Backend (`chat.py`):** Replace placeholder reflection questions with real ones. Minimum 3
  per trigger type:
  - `wrap_up`: "What was the move that unlocked this?", "Where could you have gone wrong —
    what would you watch for next time?", "Could you use the same approach on a different problem?"
  - `self_correction`: "What made you change your mind?", "How did you catch that?"
  - `escape_hatch`: "Where exactly did your thinking get stuck?", "What would you try differently?"
  - `periodic`: "What felt different about that part vs the last?", "Was there a moment you
    almost went the wrong way?"

No dependencies.

---

### 1b. Deploy script + health check + persona backup
**From:** ISSUES.md #2 | **Effort:** Low | **Owner:** Backend/DevOps

The deploy process is a list of manual commands with no script, no health check, and no rollback.

- Write `deploy/deploy.sh` wrapping git pull + pip install + frontend build + dist copy +
  nginx reload, with `set -e` and a health check against `/health` before declaring success.
- Add `GET /health` to FastAPI returning `{"status": "ok", "model": LLM_MODEL_TUTOR}`.
- Add cron entry for daily persona backup:
  `tar -czf ~/persona-backups/personas-$(date +%Y%m%d).tar.gz backend/personas/`
- Document in CLAUDE.md under Deployment.

No dependencies.

---

### 1c. Seeded dialogue tests
**From:** PLAN.md (existing) | **Effort:** Low | **Owner:** Backend

Add at least 3 seeded dialogues to `tests/test_socratic_constraints.py` using the
`fake_openrouter` fixture from `conftest.py`:
- Each dialogue is a list of `(user_message, canned_llm_reply)` pairs.
- Assert after each turn: `no_solution_leak`, `one_question`, `no_enumeration`.
- Cover: math (algebra), programming (pseudocode ask), essay (no drafted paragraph).

Assertion helpers are already wired. No dependencies.

---

## Priority 2 — Core feature gaps

Medium-to-high effort. These are the biggest functional gaps between current state and v1 complete.

### 2a. SSE streaming
**From:** ISSUES.md #6 | **Effort:** Medium | **Owner:** Both

The `/chat` endpoint returns full JSON responses. `stream_tutor()` in `llm.py` raises
`NotImplementedError`. This is visible in the demo as a response delay before anything appears.

- **Backend (`llm.py`):** Implement `stream_tutor` via OpenRouter `stream=True`. Emit
  `event: token` SSE events for each chunk of `reply`. Buffer `thinking` server-side and strip
  before streaming. After the stream completes, validate `control` and `signal`, emit `event: state`.
- **Backend (`chat.py`):** Switch `/chat` handler to use `stream_tutor`. Keep full-JSON path
  as fallback on parse failure.
- **Frontend (`client.ts`):** Implement SSE consumer — append `token` deltas to the chat
  message in real time; apply `state` event on receipt.

**No dependencies.** But shipping SSE before Critique Mode makes the live session feel
substantially more responsive, which matters for the demo.

---

### 2b. Critique Mode
**From:** ISSUES.md #3 | **Effort:** High | **Owner:** Both

`critic_base.txt` is written and the architecture supports a second mode, but there is no
entry point, no phase files, and no frontend wiring.

- **Prompt files:** Add `backend/app/prompts/v1/phase_critique.txt` and
  `phase_critique_synthesis.txt`. Phase sequence: `clarification → critique → synthesis → wrap_up`.
- **Backend:** `/session/new` accepts `mode: "critique"`. Store `artifact` in session when
  provided. When not provided, generate via `LLM_MODEL_ARTIFACT` (non-Socratic prompt with
  realistic AI output, optionally seeded with subtle errors).
- **Frontend:** After solving wrap-up, show "Want to critique an AI answer to this problem?"
  button → new session in critique mode. Also expose a second entry on the landing screen.
  Add `CritiqueArtifactPanel` (artifact display, left side) and `CritiqueFindingsList`
  (running list of student-identified issues with `verified` state).

**Dependency:** SSE (2a) makes the live Critique session feel real. Can be demoed as a static
walkthrough without SSE, but should wait for SSE before treating it as "done."

---

### 2c. Persona metrics at wrap-up + PersonaView
**From:** ISSUES.md #7 | **Effort:** Medium | **Owner:** Both

Calibration accuracy, hint usage, and reflection quality are tracked per session but never
written to the persona file. There is no UI to view the accumulated persona.

- **Backend (`chat.py`):** At session wrap-up, append a session summary to the persona file:
  `{ session_id, domain, turns, hints_used, calibration_summary, reflection_quality_summary,
  escape_hatch_used, timestamp }`. Cap at 20 sessions (drop oldest).
- **Backend:** New `GET /persona/{username}` route returns the full persona including session
  history.
- **Frontend:** Add `PersonaView` accessible from main nav. Shows inferred subject strengths,
  calibration trend across sessions, session history list. Read-only in v1.

No hard dependencies.

---

## Priority 3 — Enhancement and polish

Improvements that make the product better but don't block the demo or core functionality.

### 3a. ToolPane improvements + drawing tool + math tool refinements
**From:** ISSUES.md #4 | **Effort:** Medium | **Owner:** Frontend + Backend

- **ToolPane (frontend):** Drag-to-resize and zoom control (+ / − / reset). Remember last
  width per session.
- **Drawing tool (all domains):** Lightweight SVG-based freehand `DrawingCanvas` component,
  browser-only. Agent requests via `ui_directive`. Student submits result as `directive_response`.
- **Math graph tool:** Axis labels, gridlines, multi-expression support (`expressions: string[]`).
- **Math algebra tool:** Return intermediate steps in `display_data` so the agent can ask
  the student about a specific step rather than just the final result.

No dependencies.

---

### 3b. Multi-modal problem input + domain pill
**From:** ISSUES.md #5 | **Effort:** Medium | **Owner:** Both

Students can only type their problem. No image upload, no file attachment, no explicit domain
selection — the classifier infers the domain, which fails for handwritten problem photos.

- **Frontend (`OnboardingView` Step 2):** File/image attachment (`.jpg`, `.png`, `.pdf`, `.py`,
  `.txt`, max 2 MB). Domain pill row: `[Math] [Programming] [Essay] [Science] [Let me infer]`.
- **Backend (`/session/new`):** Accept `domain_hint: str | None` (skip classifier if provided).
  Accept `attachment` + `attachment_type`. Text files prepended to query. Images passed to
  multimodal classifier call.
- **Classifier prompt:** Handle image input — extract problem from image and classify domain.

Overlaps with F1.1 and F1.2 below; supersedes them.

---

### 3c. Backend validation rules
**From:** PROMPT_ISSUES.md P7.4 | **Effort:** Low | **Owner:** Backend

Schema rules documented but not enforced in code:
- Hint level jump guard (no skipping levels in one turn).
- `tool_call.name` domain validation (reject unregistered tool names immediately).
- `verification_prompted` required before subproblem close.
- `decomposition_source` required when subproblems first created by tutor.

No dependencies. Small, isolated additions to `chat.py` and `session.py`.

---

## Prompt-only changes (zero code, parallel track)

These require editing prompt files only. They can be done by anyone at any time without
touching the codebase. Run the affected probes afterward to verify.

### P — Physics problems misclassified as `science`
**From:** PROMPT_ISSUES.md P6.1 | **Effort:** Trivial

Physics word problems (kinematics, forces, energy) are routed to `science`, which has no
algebra or graph tools.

**Fix:** Update the classifier prompt: "Problems involving equations, calculation, or symbolic
manipulation — including physics and chemistry calculation problems — should be classified as
`math` unless they are purely conceptual or experimental."

**Verification:** Run `python -m tests.run_probes --probe json_schema_compliance` (domain
detection smoke), then test a physics query manually.

---

## Future / deferred

Items without a committed timeline. Capture here so they aren't lost.

### F1 — File attachment widget (standalone)
**From:** PLAN.md (existing F1.1)

Superseded by 3b above if that lands first. Keep as fallback if 3b is descoped.
Frontend-only: `AttachmentChip` component, `FileReader.readAsText`, prepend to query.
For images: multimodal content block in `build_prompt`. Files > 2 MB rejected inline.

### F2 — Subject/domain hint widget (standalone)
**From:** PLAN.md (existing F1.2)

Superseded by 3b above. Pill row in `OnboardingView` Step 2, `domain_hint` field in
`POST /session/new`, classifier bypass if hint provided. Simpler than the full 3b scope.

### F3 — Seeded-flaw artifact generation (Critique Mode v1.1+)
**From:** CLAUDE.md design doc

Generated artifacts for Critique Mode get a secondary editing pass that inserts a subtle
error, raising critique difficulty and making the mode more pedagogically interesting.
Depends on Critique Mode (2b) being shipped first.

### F4 — Science specialization (MVP)
**From:** CLAUDE.md

`science` and `general` are scaffolded but not full MVP specializations. Science needs more
tool guidance and a clearer scope (school physics vs. biology vs. chemistry). Low urgency
given math, programming, and essay cover the demo.

---

## Dependency map

```
1a (reflection fix)  ──── no deps
1b (deploy script)   ──── no deps
1c (seeded tests)    ──── no deps
P  (classifier fix)  ──── no deps

2a (SSE streaming)   ──── no deps
2b (Critique Mode)   ──── 2a preferred first (live feel)
2c (persona metrics) ──── no deps

3a (tool polish)     ──── no deps
3b (multimodal)      ──── supersedes F1, F2
3c (backend guards)  ──── no deps

F3 (seeded flaws)    ──── needs 2b
```
