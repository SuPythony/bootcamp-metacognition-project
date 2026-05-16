# Known Issues & Recommended Changes

Seven items. Engineering issues first, then product additions. Each has a
clear owner (backend / frontend / both) and a scope note.

---

### 1 — Wrap-up reflection is fragile; defaults are weak

**What's wrong:** `emit_reflection: "wrap_up"` fires correctly but the
session can close before the student responds — the SSE connection drops or
the frontend transitions state before the card renders. Additionally, the
backend question bank for all four trigger types (`periodic`,
`self_correction`, `escape_hatch`, `wrap_up`) contains placeholder entries
that don't produce meaningful reflection.

**Root cause (confirmed 2026-05-17 in manual testing):**
`frontend/src/views/SessionView.tsx:186-188` schedules `onWrapUp` 1.8 s
after the **first** turn whose phase is `wrap_up` — exactly the turn the
agent asks the synthesis question on. The student sees the question for a
beat, then `WrapUpView` replaces the chat before they can answer. The
designed multi-turn wrap-up dialogue (synthesis Q&A → look-back Q&A →
closing message, per `phase_wrap_up.txt:35-46`) is collapsed into a single
unanswered turn. The prompt explicitly says *"The session ends after the
reflection response is received — not when the synthesis question is
asked."* — the frontend ignores this.

`ChatResponse` (`chat.py:212-223`) carries no `session_complete` field, so
the frontend has no way to distinguish "first wrap_up turn" from "wrap_up
dialogue is finished."

**Actions:**
- **Backend (`chat.py`):** Add a `session_complete: bool` field to
  `ChatResponse`, set deterministically (NOT via an agent signal — same
  dormancy risk as `emit_reflection`) when `signal.last_reflection_quality`
  arrives against a `trigger="wrap_up"` reflection. This is the moment the
  agent has heard and evaluated the student's synthesis response, after
  which it's safe to close. Mirror the pattern used for `initial_understanding`
  capture (deterministic, idempotent, no reliance on agent signalling).
- **Frontend (`SessionView.tsx:186-188`):** Change the transition trigger
  from `res.phase === "wrap_up"` to `res.session_complete`. Keep the
  manual "Done — see your thinking trace" button at line 363 as the
  fallback for sessions where the agent fails to wrap properly.
- **Backend (`chat.py`):** The reflection question bank needs real questions.
  Minimum 3 per trigger type. Wrap-up examples: "What was the move that
  unlocked this?", "Where could you have gone wrong — what would you watch
  for next time?", "Could you use the same approach on a different problem?"
  Self-correction: "What made you change your mind?", "How did you catch that?"
  Escape hatch: "Where exactly did your thinking get stuck?", "What would you
  try differently?" Periodic: "What felt different about that part vs the
  last?", "Was there a moment you almost went the wrong way?"

---

### 2 — Deployment routines are manual and undocumented

**What's wrong:** The deploy process in CLAUDE.md is a list of manual
commands with no script, no health check, no rollback path, and no
confirmation that the new build is serving before traffic switches.

**Actions:**
- Write `deploy/deploy.sh` — wraps the four manual steps (git pull, pip
  install, build frontend, copy dist, reload nginx) with basic error
  handling (`set -e`) and a health check against `/health` before declaring
  success.
- Add a `GET /health` route to FastAPI returning `{"status": "ok",
  "model": LLM_MODEL_TUTOR}` — confirms the server is up and the env is
  configured.
- Add a cron entry for daily persona backup: `tar -czf
  ~/persona-backups/personas-$(date +%Y%m%d).tar.gz backend/personas/`
- Document all three in CLAUDE.md under a Deployment section.

---

### 3 — Critique Mode missing; entry point not surfaced

**What's wrong:** `critic_base.txt` is written and the architecture supports
a second mode, but there is no entry point, no phase files, and no frontend
wiring. The demo answers only half the brief's question.

**Actions:**
- **Prompt files:** Add `backend/app/prompts/v1/phase_critique.txt` and
  `backend/app/prompts/v1/phase_critique_synthesis.txt` using `critic_base.txt`
  as source material. The Critique Mode phase sequence is:
  `clarification → critique → synthesis → wrap_up`.
- **Backend:** `/session/new` accepts `mode: "critique"` (currently rejected).
  When `artifact` is provided in the body, store it in session state.
  When not provided, generate one via a separate `LLM_MODEL_ARTIFACT` call
  (non-Socratic prompt; realistic AI output including subtle errors).
- **Frontend:** After the solving wrap-up, show a single button:
  "Want to critique an AI answer to this problem?" — routes to a new session
  in critique mode with the same problem. Also expose a second entry on the
  landing screen: "Evaluate something an AI wrote."
- **UI:** Add `CritiqueArtifactPanel` (left side, shows the artifact) and
  `CritiqueFindingsList` (running list of student-identified issues with
  `verified` state).

---

### 4 — Tooling needs refinement and a universal drawing tool

**What's wrong:** Math algebra and graph tools are functional but the graph
tool has no interactivity and no resize. No domain has a drawing/diagram
tool. The ToolPane is fixed-size and cannot be zoomed or resized, making
graphs and tables hard to read.

**Actions:**
- **ToolPane (frontend):** Add drag-to-resize and a zoom control (+ / - /
  reset). The panel should remember its last width per session.
- **Drawing tool (all domains):** Add a lightweight SVG-based freehand
  drawing tool — `DrawingCanvas` component. No backend needed; runs entirely
  in the browser. The student can sketch a diagram, label it, and submit it
  as a `directive_response`. Available in all domains; the agent can request
  it via `ui_directive` with `component: "DrawingCanvas"`.
- **Math graph tool:** Add axis labels, gridlines, and the ability to plot
  multiple expressions on one chart. Accept `expressions: string[]` in args
  alongside the existing `expression`.
- **Math algebra tool:** Return intermediate steps not just the final result,
  so the model can ask the student about a specific step.

---

### 5 — Problem input is text-only; classification requires manual domain selection

**What's wrong:** Students can only type their problem. There is no image
upload, no file attachment, and no way to indicate the domain — the
classifier infers it, which fails for photos of handwritten problems or
ambiguous queries.

**Actions:**
- **Frontend (`OnboardingView` Step 2):** Add a file/image attachment button
  (`.jpg`, `.png`, `.pdf`, `.py`, `.txt` — max 2 MB). Show filename chip with
  remove. Add a domain pill row: `[Math] [Programming] [Essay] [Science] [Let
  me infer]` — default is infer.
- **Backend (`/session/new`):** Accept `domain_hint: str | None` and
  `attachment: base64 | None` with `attachment_type`. If `domain_hint` is
  provided, skip the classifier. If attachment is an image and no hint,
  pass image + query to the multimodal classifier call. Text files are
  prepended to the query string.
- **Classifier prompt:** Update to handle image input when provided — extract
  the problem from the image and classify domain simultaneously.

---

### 6 — SSE streaming is stubbed; `/chat` returns full responses

**What's wrong:** The `/chat` endpoint currently returns complete JSON
responses rather than streaming tokens. `stream_tutor` raises
`NotImplementedError`. This makes the chat feel unresponsive on long
replies and is a visible demo issue.

**Actions:**
- **Backend (`llm.py`):** Implement `stream_tutor` using the OpenRouter
  streaming API (`stream=True`). Emit `event: token` SSE events for each
  chunk of `reply`. After the stream completes, validate the assembled
  `control` and `signal` blocks and emit `event: state`.
- **Backend (`chat.py`):** Switch `/chat` to use `stream_tutor`. Handle
  the `thinking` field: buffer it server-side, strip before streaming any
  token to the client.
- **Frontend (`client.ts`):** Implement the SSE consumer — append `token`
  deltas to the chat message in real time; apply `state` event on receipt.
- The non-streaming JSON path remains as fallback if SSE fails.

---

### 7 — Persona stores minimal data; no way to view or build it

**What's wrong:** Personas currently store only the two onboarding fields
plus inferred subject confidence. Calibration accuracy, hint usage patterns,
session count, and reflection quality are tracked in sessions but never
written to the persona file. There is no UI to view or create a persona
without starting a problem session.

**Actions:**
- **Backend (`chat.py`):** At session wrap-up, append a session summary to
  the persona file: `{ session_id, domain, turns, hints_used,
  calibration_summary: {predicted, outcomes}, reflection_quality_summary,
  escape_hatch_used: bool, timestamp }`. Cap the history at 20 sessions
  (drop oldest).
- **Backend (`/persona/view`):** New `GET /persona/{username}` route returns
  the full persona file including session history.
- **Backend (`/persona/create` standalone):** Allow creating a persona with
  just a username and the two onboarding questions, without starting a
  problem session. The existing onboarding flow already does this — expose
  it as a standalone entry point.
- **Frontend:** Add a `PersonaView` accessible from the main nav. Shows:
  age/school level, inferred subject strengths/difficulties, calibration
  trend across sessions ("you've been getting more accurate"), and session
  history list. Read-only in v1 — no editing.

---

## Summary

| # | What | Owner | Effort |
|---|---|---|---|
| 1 | Wrap-up reflection bug + question bank defaults | Frontend + Backend | Low |
| 2 | Deploy script + health check + persona backup cron | Backend/DevOps | Low |
| 3 | Critique Mode: prompts, backend mode, frontend entry + panels | Both | High |
| 4 | ToolPane resize/zoom + drawing tool + math tool improvements | Frontend + Backend | Medium |
| 5 | Multi-modal problem input + domain pill + classifier update | Both | Medium |
| 6 | SSE streaming implementation | Both | Medium |
| 7 | Persona metrics at wrap-up + PersonaView + standalone onboarding | Both | Medium |