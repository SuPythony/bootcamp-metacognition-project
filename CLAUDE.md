# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Current State

**Scaffolded; design expanded; no domain logic yet.** The repository now contains the full directory structure described in "Repository Layout" below, with stub files in place. The six locked-in decisions and the new v1 design additions (Critique Mode, Reflection & Calibration subsystem, short onboarding with passive persona capture, AWS EC2 deployment) shape what gets built next.

- `backend/` — FastAPI app shell, the Socratic base prompt at `backend/app/prompts/socratic_base.txt`, the Critic-Coach base prompt at `backend/app/prompts/critic_base.txt`, and all six specializations each with `__init__.py`, `prompt.txt`, and `manifest.json`. Math and programming carry tool stubs.
- `frontend/` — Vite + React + Tailwind + TypeScript shell, typed API client (`client.ts`, `types.ts`, `mock.ts`), domain-agnostic component shells, specialization registry, per-domain `.tsx` component shells matching each `manifest.json`'s `ui_components` catalog.
- `reflections/` — team journals, ignore for engineering work.

What's a stub vs. what's real:

- **Real and frozen**: directory layout, manifest schemas, `api/types.ts` shape (needs an update pass for mode/artifact/critique fields), dependency manifests, the two base prompts (socratic_base.txt and critic_base.txt).
- **Stubs**: FastAPI routes return placeholders; React components render placeholders; tool modules raise `NotImplementedError`; plugin registry loader is not wired; mock.ts only covers the happy path of one endpoint; no critique-mode UI components exist yet.

Next milestones, in order: plugin registry loader → `/chat` SSE relay with JSON-schema validation → math specialization (school-level) end-to-end in solving mode → critique mode → deploy. See "What to Build First (MVP cut + stretch)" for the full sequence.

---

## Commands

### Backend (`backend/`)

```
# install (editable, with dev + math extras)
pip install -e ".[dev,math]"

# run the API (port 8000, auto-reload)
uvicorn app.main:app --reload

# tests
pytest
pytest tests/test_plugin_registry.py        # single file
pytest -k "test_socratic_constraint"        # single test by name

# lint / format
ruff check .
ruff format .
```

Required env vars (see `backend/.env.example`):
- `LLM_MODEL_TUTOR` — main tutor model identifier (OpenRouter)
- `LLM_MODEL_CLASSIFIER` — cheap model for domain detection
- `OPENROUTER_API_KEY`

### Frontend (`frontend/`)

```
# install
npm install

# dev server (port 5173)
npm run dev

# typecheck
npm run typecheck

# production build
npm run build
npm run preview                              # serve the build locally
```

Required env vars (see `frontend/.env.example`):
- `VITE_API_URL` — backend URL (default `http://localhost:8000`)
- `VITE_USE_MOCK` — `true` to use the in-browser mock, `false` to hit the backend

Frontend has no linter configured yet; rely on `tsc` via `npm run typecheck`.

---

## Decisions (locked in)

The six integration-shape decisions below were debated and confirmed. They are now load-bearing for the rest of this doc — changes to any of them require updating dependent sections in the same PR.

1. **Agent structured output** — single JSON object via OpenRouter structured outputs (JSON Schema mode). Shape: `{ "reply": "...", "control": { ... } }`. Fallback: JSON mode + Pydantic parsing with one retry on parse failure.
2. **Streaming** — Server-Sent Events on `/chat`. Two event types: `token` (chunks of `reply`) and `state` (validated `control` object at end). Non-streaming JSON is the fallback if SSE proves fiddly.
3. **Agent decision authority** — agent owns all phase transitions, hint escalation, subproblem creation, tool calls, mode-specific decisions. Backend is a validator: rejects illegal moves (phase skip, hint jump > +1), never silently overrides; rejection returns an error event the frontend handles as a soft retry.
4. **Domain detection** — runs inside `/session/new` using `query` as input via `LLM_MODEL_CLASSIFIER` (a cheap model, separate from `LLM_MODEL_TUTOR`). `query` is stored as the first user message; `opening_message` is the tutor's first reply, produced in the same call.
5. **Onboarding mechanism** — runs through `/chat` with reserved domain `"persona"` (a specialization at `backend/specializations/persona/`). See "Login & Persona Flow" for the shortened v1 flow.
6. **Username required** on `/session/new`. No anonymous sessions in v1.

---

### Open follow-ups (not blocking v1 build, but decide soon)

- **Code runner sandboxing.** The `programming` specialization will execute student code via `/tools/run-code`. Choose: subprocess + `resource` limits + seccomp, Docker exec, or in-browser Pyodide. v1 must not leave this as "TODO sandbox" in production code.
- **Type sync between frontend/backend.** Generate `frontend/src/api/types.ts` from FastAPI's OpenAPI schema rather than mirroring by hand. One-time setup, removes a whole class of drift bugs.
- **History truncation.** v1 sends full `message_history` every turn. Acceptable for demos, breaks past ~50 turns. Defer to v2.
- **Frontend lint.** No ESLint/Prettier configured yet. `npm run typecheck` (tsc) is the only frontend gate. Decide whether to add ESLint before deploy or accept tsc-only for v1.

---

## Repository Layout

The repo is split into two top-level project folders that can be developed, run, and deployed independently. They communicate only over HTTP (the contract is the API in "API Endpoints" below).

```
bootcamp-metacognition-project/
├── backend/                    ← Python + FastAPI
│   ├── app/                    ← FastAPI application code
│   │   ├── main.py             ← FastAPI entrypoint, route mounting
│   │   ├── chat.py             ← /chat, /session/new handlers
│   │   ├── persona.py          ← /persona/create, /persona/reset handlers
│   │   ├── session.py          ← in-memory session store + Session model
│   │   ├── plugin_registry.py  ← folder-scanning loader, tool dispatcher
│   │   ├── llm.py              ← OpenRouter client (reads LLM_MODEL env var)
│   │   └── prompts/
│   │       └── socratic_base.txt   ← universal Socratic rules, prepended to every domain prompt
│   ├── specializations/        ← one folder per domain; see "Specialization Plugin System"
│   │   ├── math/
│   │   ├── programming/
│   │   ├── essay/
│   │   ├── science/
│   │   └── general/
│   ├── personas/               ← runtime persona JSON files (gitignored except .gitkeep)
│   ├── tests/
│   ├── pyproject.toml          ← or requirements.txt — pin during scaffold
│   └── .env.example            ← LLM_MODEL, OPENROUTER_API_KEY, etc.
│
├── frontend/                   ← React + Vite + Tailwind
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                ← typed client for the backend API contract
│   │   │   ├── client.ts       ← fetch wrapper, base URL from VITE_API_URL
│   │   │   ├── types.ts        ← mirrors backend schemas (Session, Subproblem, ThinkingTrace, Persona)
│   │   │   └── mock.ts         ← in-browser mock that satisfies the contract; toggle via VITE_USE_MOCK
│   │   ├── components/         ← domain-agnostic: ChatPane, SubproblemPanel, ToolPane, HintBadge, ConfidenceWidget, ThinkingTraceDrawer
│   │   ├── specializations/    ← domain-specific UI components, mirrored 1:1 with backend/specializations/
│   │   │   ├── registry.ts     ← maps "<domain>.<component>" → React component (single source for lookup)
│   │   │   ├── math/           ← AlgebraSteps.tsx, GraphView.tsx
│   │   │   ├── programming/    ← CodeOutput.tsx, PseudocodePad.tsx
│   │   │   ├── essay/          ← OutlineTree.tsx
│   │   │   └── science/        ← GraphView.tsx, DataTable.tsx
│   │   ├── views/              ← OnboardingView, SessionView, WrapUpView
│   │   └── styles/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.example            ← VITE_API_URL, VITE_USE_MOCK
│
├── reflections/                ← team journals, NOT code (ignore for engineering tasks)
└── CLAUDE.md
```

### Cross-cutting rules

- The **API contract** in this file (see "API Endpoints") is the integration boundary between `frontend/` and `backend/`. Contract changes require updating both sides plus this doc in the same change — otherwise the frontend mock and the backend diverge.
- Frontend never imports from `backend/` and vice versa. Shared shapes are mirrored by hand in `frontend/src/api/types.ts`; if schemas drift, fix `types.ts` from this CLAUDE.md.
- The frontend must work standalone against `VITE_USE_MOCK=true` so UI work isn't blocked by backend progress.
- A **specialization is a pair**: `backend/specializations/<domain>/` (prompt, tools, manifest) AND `frontend/src/specializations/<domain>/` (React components the agent can ask to render). The two halves are coupled by names declared in `manifest.json`'s `ui_components` list — see "Specialization UI Contract" below. Adding a new domain means landing both folders together.
- The frontend discovers domains and their component catalog via `GET /specializations`; it must not hardcode domain names. Components are looked up by `"<domain>.<component_name>"` through `frontend/src/specializations/registry.ts`.
- The frontend must work standalone with `VITE_USE_MOCK=true`. The mock layer must emit the same `ui_directives` shape a real backend would, so component rendering is exercised in mock mode too.
- Paths shown elsewhere in this doc (e.g. `app/prompts/socratic_base.txt`, `personas/{username}.json`, `specializations/math/prompt.txt`) are relative to `backend/` unless prefixed with `frontend/`.

---

# Socratic Tutor App

> **Core philosophy**: The AI never solves the problem for the student.
> It guides them to solve it themselves by surfacing their own understanding,
> decomposing the problem collaboratively, and nudging — never telling.

> **Design thesis**: In an AI-rich world, the ability to frame problems, judge
> outputs, and monitor one's own thinking matters more, not less. Every feature
> of this app should strengthen one of those behaviours — not shortcut it.
> Students learn by doing: through decision-making, decomposition, and reflection.
> Never by reading tips or watching the AI perform.

---

## Project Overview

A web-based learning tool for **teenagers (roughly 13–18)** that strengthens thinking skills which stay valuable in an AI-rich world: framing problems, checking understanding, calibrating confidence, reflecting on mistakes, and **judging AI outputs**. Built for the [Metacognition Vibe Coding Task](https://docs.tk.sg/Metacognition-Vibe-Coding-Task-551dd9d8b64483d7942101e280188fdb).

The product is two cooperating loops served from one chat interface:

1. **Solving Mode** — student brings a school-level problem (algebra, intro programming, essay outline, science question). A Socratic tutor agent guides them to construct the solution themselves, never giving the answer. The "show and do, don't tell" mandate from the brief lives here.
2. **Critique Mode** — student brings an AI-generated artifact (a ChatGPT solution, a code snippet, an essay draft) or asks for one to be generated. A Critic-Coach agent guides them to evaluate it: spot errors, surface what's missing, distinguish confident-sounding from correct. This is the "judging AI outputs" axis the brief specifically asks for.

Both modes share the same plumbing — same `/chat` endpoint, same plugin system, same thinking-trace surface. They differ in agent prompt and the phase sequence they walk through.

**Target audience constraints**:
- Examples and tone calibrated for teens (school subjects, not undergraduate).
- Short onboarding (2 questions max) to lower drop-off; remainder of the persona is captured passively from conversation.
- Engagement loop matters: visible progress, agency in mode/domain choice, a thinking trace at the end that feels like a reward not a report card.

**Current scope (v1)**:
- Solving Mode + Critique Mode
- Two specializations as MVP: `math` (school-level algebra and arithmetic) and `programming` (intro Python / pseudocode). `essay`, `science`, and `general` are scaffolded but not MVP — ship them only after MVP holds together.
- Periodic reflection prompts + end-of-session thinking trace
- Calibration tracking (predict-then-check)
- Persona persistence per username, JSON files on disk
- Deployed on the team's AWS EC2 instance (see "Deployment")
- No auth tokens, no cloud DB, no cross-session learning

---

## Login & Persona Flow

**Design intent**: get the student into a productive session as fast as possible. Onboarding asks the minimum, then the rest of the persona is **inferred passively** from how they talk during early sessions. Long form-based intake kills teen drop-off; this product never has one.

### Onboarding flow (v1)

1. User enters a username (no password — this is identity, not auth).
2. App checks `backend/personas/{username}.json`. If it exists → skip to session.
3. If not: a 2-turn welcome runs via `/chat` against the reserved `"persona"` domain:
   - Turn 1: "Hey, before we dive in — what's your age or school year?" *(Captures: age band, school level)*
   - Turn 2: "Cool. What brings you here today — a specific problem, or just exploring?" *(Captures: initial intent, anchors the first session)*
4. The persona agent writes a **stub persona** (age band + initial intent + `created_at` only) and routes the student into the first real session.
5. From that session onward, every `/chat` response may include a `control.persona_updates` block that merges into the persona file: inferred education level (from problem complexity), inferred confident/difficult subjects (from which domains they pick and how they handle them), inferred learning style (from which hint levels land vs. miss). Fields gain an `inferred: true` flag when set this way.

The persona file is therefore **partial on day 1 and grows**. The system prompt always notes which fields are inferred vs. asked, so the agent treats inferred signals as hypotheses, not facts.

### Persona JSON schema (`backend/personas/{username}.json`)

```json
{
  "username": "alex",
  "created_at": "2026-05-14T00:00:00Z",
  "age_band": "13-15 | 16-18 | other",
  "school_level": "lower_secondary | upper_secondary | other",
  "initial_intent": "free-form sentence from onboarding turn 2",
  "education_detail": { "value": "year 10", "inferred": false },
  "confident_subjects": [{ "value": "linear equations", "inferred": true, "evidence": "solved sp-1 of session abc without hints" }],
  "difficult_subjects": [{ "value": "word problems", "inferred": true, "evidence": "escape hatch used twice in session abc" }],
  "learning_style": { "value": "examples_first", "inferred": true },
  "preferred_pace": { "value": "medium", "inferred": true },
  "goals": { "value": "pass next math test", "inferred": false }
}
```

Every non-trivial field is `{ value, inferred, evidence? }`. The agent reads inferred fields with appropriate uncertainty ("I've noticed you seem comfortable with X — does that feel right?") and can ask a confirming question to upgrade `inferred: true → inferred: false`.

### Persona injection (per session)

```python
def build_prompt(session: Session, user_message: str) -> list[dict]:
    persona_ctx = f"Student profile:\n{session.persona.to_context_str()}" if session.persona else ""
    return [
        {"role": "system", "content": SOCRATIC_BASE + DOMAIN_SYSTEM_PROMPTS[session.domain]},
        {"role": "system", "content": persona_ctx},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
        {"role": "user", "content": user_message}
    ]
```

`persona.to_context_str()` returns a short natural-language summary:
> *"The student is a 2nd-year CS undergraduate. Confident in linear algebra and Python. Finds probability and recursion difficult. Prefers examples before theory. Goal: prepare for algorithms exam."*

### Persona update (optional, v1)

A `/persona/reset` route clears the file and reruns onboarding. No in-session updates in v1.

### Storage

- Personas stored as JSON files in `backend/personas/` (server-side; gitignored).
- No encryption in v1 — no sensitive data is collected.
- Username is the only identifier; no passwords, no email.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind |
| Backend | Python + FastAPI |
| LLM routing | OpenRouter (model-agnostic; no model hardcoded — set via `LLM_MODEL` env var) |
| Tool execution | FastAPI endpoints (algebra CAS, code runner, graphing) |
| Session state | In-memory (server-side, keyed by session ID) |
| Auth | None (v1 — simple username entry for persona persistence) |

---

## Architecture

The frontend and backend are independent projects. Their only coupling is HTTP — see "API Endpoints".

```
frontend/  (React + Vite + Tailwind, port 5173)
  Browser
   │
   ├── ChatPane            ← primary interaction surface
   ├── SubproblemPanel     ← decomposition tree, built collaboratively
   ├── ToolPane            ← renders tool output for whichever specialization is active
   └── ThinkingTraceDrawer ← session reflection (shown at end)
        │
        │  HTTP (VITE_API_URL → http://localhost:8000 in dev)
        │  ── or ── in-browser mock when VITE_USE_MOCK=true
        ▼
backend/  (Python + FastAPI, port 8000)
  app/
   ├── POST /chat                          ← main message relay, carries session state
   ├── POST /session/new                   ← initialise session, detect domain
   ├── POST /tools/{tool_name}             ← generic tool dispatch (routes to registered plugins)
   ├── GET  /session/{id}/thinking-trace   ← return session reflection object
   ├── POST /persona/create | /persona/reset
   └── GET  /specializations               ← discovery: lists registered domains + tools
        │
        ▼
backend/specializations/  (Plugin Registry — folder-scanned at startup)
   ├── math/           ← registers: algebra (sympy), graph (matplotlib)
   ├── programming/    ← registers: code_runner (sandboxed exec)
   ├── essay/          ← registers: (no tools in v1; prompt-only)
   ├── science/        ← registers: graph, data_table
   └── [future]/       ← drop a new folder in, register tools + prompt, done
        │
        ▼
OpenRouter  →  configured model via LLM_MODEL env var (teaching persona)
              (tool calls invoke registered plugin endpoints)
```

---

## Session State Schema

Kept server-side, passed back to LLM as context on each turn.

```json
{
  "session_id": "uuid",
  "mode": "solving | critique",
  "domain": "math | programming | essay | science | general",
  "original_query": "...",
  "artifact": null,
  "phase": "clarification | decomposition | solving | critique | synthesis | wrap_up",
  "initial_understanding": "student's articulated understanding (captured in clarification phase)",
  "initial_critique": null,
  "subproblems": [
    {
      "id": "sp-1",
      "description": "...",
      "goal": "what the student says this part should achieve",
      "status": "pending | active | solved",
      "hints_given": 0,
      "direct_answer_requested": false,
      "escape_hatch_reflection": null,
      "confidence_score": null
    }
  ],
  "active_subproblem_index": 0,
  "critique_findings": [
    { "id": "f-1", "claim": "student-stated issue with the artifact", "kind": "factual_error | reasoning_gap | missing_step | overconfident_language | other", "verified": false }
  ],
  "calibration_points": [
    { "subproblem_id": "sp-1", "predicted_confidence": 4, "outcome": "correct | wrong | partial", "noted_at": "iso8601" }
  ],
  "reflection_prompts": [
    { "trigger": "periodic | self_correction | escape_hatch | wrap_up", "question": "...", "response": "...", "quality": "shallow | decent | deep | null" }
  ],
  "persona_updates_pending": [],
  "metrics": {
    "turns_total": 0,
    "clarification_turns": 0,
    "decomposition_turns": 0,
    "hints_per_subproblem": [],
    "direct_answer_requests": 0,
    "self_corrections": 0,
    "phase_timestamps": {}
  }
}
```

- `mode` is fixed at `/session/new` and never changes within a session.
- `artifact` is the AI-generated content under critique; only populated when `mode = critique`. Either the student pastes it, or the system generates it (see Critique Loop).
- `phase` set differs by mode (see Modes below).
- `critique_findings` are issues the student names; `verified` flips when the critic-coach agrees the issue is real after Socratic probing.
- `calibration_points` are predict-then-check records — see Reflection & Calibration subsystem.
- `reflection_prompts` records every reflection the agent asks for, the student's answer, and the agent's later quality assessment of that answer.

---

## Modes

A session is in one of two modes, fixed at creation time. Both share the same `/chat` plumbing, plugin system, and thinking-trace surface; the agent's system prompt and phase sequence change.

### Solving Mode (default)
The student brings a problem; the agent guides them to construct the solution. Phase sequence: `clarification → decomposition → solving → wrap_up`. The classic Socratic loop documented below.

### Critique Mode
The student brings (or asks the system to generate) an AI artifact — a worked solution, an essay paragraph, a code snippet — and the agent guides them to evaluate it. Phase sequence: `clarification → critique → synthesis → wrap_up`. This is the "judge AI outputs" axis the brief calls for. Full description in "The Critique Loop" below.

The frontend exposes mode at session creation as a two-button choice on the landing screen: *"Bring a problem"* (solving) or *"Bring something an AI wrote"* (critique). A third path — *"Let the AI try first, then I'll critique it"* — creates a critique session whose `artifact` is generated by a separate non-Socratic LLM call seeded with the student's prompt.

---

## The Solving Loop (CRITICAL — core of the product)

This is the heart of the app. Every design decision should serve this flow.

### Phase 0 — Domain Detection (automatic, 1 LLM call)

On the first user message, a fast classification call determines:
- `domain`: math | programming | essay | science | general
- `complexity_hint`: single-step | multi-step | open-ended

This selects the **domain system prompt** and the available **UI components**.

---

### Phase 1 — Clarification (student articulates understanding first)

**Rule**: The AI does NOT engage with the problem until the student has stated their own understanding.

System prompt instruction:
```
You are a Socratic tutor. The student has just submitted a problem.
Do NOT attempt to solve it or hint at the solution.
Ask 1–2 targeted questions to surface what the student already understands
about this problem. Wait for them to answer before proceeding.
Capture their response as their "initial_understanding".
```

The AI should ask things like:
- *"Before we dig in — what's your current thinking on this? Even a rough intuition is fine."*
- *"What part feels clear to you right now, and what feels murky?"*
- *"Have you seen a problem like this before? What did you try?"*

**Exit condition**: Student has articulated some initial understanding (even "I have no idea where to start" is valid — note it and move on).

---

### Phase 2 — Collaborative Decomposition

**Rule**: The AI never lists the subproblems. It nudges the student to identify them.

System prompt instruction:
```
The student has stated their initial understanding. Now help them decompose
the problem into meaningful parts. Do NOT enumerate the subparts yourself.
Ask questions that help the student discover the natural sub-structure:
- "What would you need to figure out first before you can tackle the whole thing?"
- "If you solved this smaller piece, how would that help with the rest?"
- "Can you break this into steps? What's the first step you'd take?"
Accept each part the student proposes. Ask them to state the *goal* of each part
(what does solving it achieve?). Build the subproblem list from their responses.
When the student seems satisfied with the breakdown, confirm it and move to solving.
```

**UI**: The `SubproblemPanel` renders the decomposition tree live as the student proposes parts. Each node shows: description, goal, status.

**Exit condition**: Student confirms the decomposition (or AI gently suggests they may be missing a key piece via a question, never a statement).

---

### Phase 3 — Solving Loop (per subproblem)

For each subproblem, in order:

#### 3a. Activation
- AI announces the active subproblem and asks the student to attempt it.
- *"Okay, let's work on [sp-1]. What's your first instinct here?"*

#### 3b. Hint Ladder (escalating nudges)
Each wrong turn or "I'm stuck" gets a hint, not an answer. Hints escalate:

| Hint Level | Style |
|---|---|
| 1 | Conceptual question (*"What does X mean in this context?"*) |
| 2 | Reframe (*"What if you thought about it as…?"*) |
| 3 | Point to a foundational concept (*"Do you remember how [relevant concept] works?"*) |
| 4 | Worked analogy (*"Here's a similar but simpler case — does this help?"*) |
| 5 | Near-direct (*"You're very close. The key insight is [vague direction]."*) |

Hint level is tracked in session state (`hints_per_subproblem`).

#### 3c. Tool Offload (mechanical sub-tasks)
When a subproblem requires:
- **Algebra / symbolic manipulation** → call `/tools/algebra` (sympy), show steps in ToolPane
- **Graphing** → call `/tools/graph`, render in ToolPane, let student interpret
- **Code execution** → call `/tools/run-code`, show output, ask student to interpret it
- **Standard algorithm** → provide the implementation via tool, ask student to explain what it does

The AI never presents tool output as "the answer." It presents it as data for the student to reason about.

#### 3d. Confidence Check (after each subproblem)
When a subproblem is resolved:
- *"How confident are you in this solution? 1–5?"*
- *"Is there anything about this step you're still unsure about?"*
- *"Could you explain why this works to someone else?"*

Low confidence → one more round of questions before moving on.

#### 3e. Soft Escape Hatch (direct answer, rare)
If the student explicitly asks for the answer multiple times, or signals strong frustration:

1. First: *"I can tell you're stuck. Do you want a strong hint, or do you want me to just show you this step?"*
2. If they confirm "just show me": **before giving the answer**, ask them to write one sentence: *"Before I show you — in one sentence, where exactly did your thinking get stuck?"*
3. Store their response as `escape_hatch_reflection` in the thinking trace.
4. Then provide the answer for *that subproblem only* and continue the loop.

**Why the reflection step matters**: it turns the failure mode into a metacognitive moment. The student practises noticing their own stuck-point, which is the skill the app is building. It also makes the escape hatch feel earned rather than cheap. Never skip this step — even if the student resists, prompt once more before proceeding.

The answer is never offered proactively. Escape hatch is per-subproblem only.

---

### Phase 4 — Wrap-Up

After all subproblems are solved:
1. AI asks the student to synthesize: *"Can you now explain the full solution in your own words?"*
2. Compare their current explanation to their `initial_understanding` — surface the delta.
3. Generate session metrics summary (see Metrics section).

---

## The Critique Loop (CRITICAL — second core flow)

This is the second teaching loop and the product's strongest answer to the brief's "judge AI outputs" directive. Same Socratic discipline as Solving, inverted: the AI produces or imports the content; the student evaluates it.

### Setup

A critique session starts with an `artifact` — a worked AI solution, an essay, a code snippet, an explanation. Two ways it gets there:

- **Imported**: student pastes content they got from another AI (ChatGPT, school chatbot, classmate's GPT use) into the input on the landing screen.
- **Generated**: student types a prompt ("solve this differential equation", "write a paragraph arguing X"), and the backend calls a **separate, non-Socratic LLM** (`LLM_MODEL_ARTIFACT`, may be the same as `LLM_MODEL_TUTOR`) to produce the artifact. The system prompt for this call is *not* the Socratic base — the goal is to produce realistic AI output, including realistically subtle errors. The artifact may be deliberately seeded with one or two introduced flaws via a secondary editing pass (v2; v1 takes the LLM's first response unmodified).

The artifact is stored in `session.artifact` and shown to the student in a dedicated `CritiqueArtifactPanel` on the left. The right side is the chat with the Critic-Coach.

### Phase C0 — Initial Read (silent first impression)

Before the coach engages, the student is asked for an `initial_critique` — one sentence: *"On first read, what's your gut feeling about this?"* This anchors a comparison at wrap-up, parallel to `initial_understanding` in solving.

### Phase C1 — Clarification

The coach asks the student to articulate what the artifact is *claiming*. Many critique failures happen because the student didn't parse the claim carefully. *"In your own words, what is this trying to convince you of?"* Captures their understanding before they evaluate.

### Phase C2 — Critique (per finding, escalating depth)

The student names issues; each becomes a `critique_finding`. For each finding:

**C2a. Surface the finding.**
The student says what they think is wrong. The coach **never confirms or denies on the spot**. *"Walk me through where you see that. What specifically in the text gave you that read?"*

**C2b. Test the finding (the key Socratic move).**
The coach probes: *"What would you expect to see if this part were correct?"* / *"Could there be a version of this where what they wrote is right?"* / *"How would you check?"* The student either strengthens the finding (verified = true) or retracts it (a self-correction — celebrated, noted in metrics).

**C2c. Tool offload when applicable.**
For math critiques, the coach may invoke the algebra tool to actually evaluate a step the student suspects. For code critiques, invoke the code runner on a suspicious section. Tool output is data, not verdict — the student interprets it.

**C2d. Coverage check.**
After the student says they're done, the coach asks once: *"Anything in this artifact you didn't look at carefully?"* This is the only place the coach may gently surface an issue the student missed — and only as a question, never as a statement. (*"What do you make of the third paragraph's claim about X?"* not *"They got X wrong."*)

Hint ladder applies as in Solving: if the student is stuck on a finding (says "I dunno, something feels off"), the coach escalates by exactly one level per turn. Level 5 is *"have a closer look at [vague region]"* — never *"here's the bug."*

### Phase C3 — Synthesis

The student writes their final verdict on the artifact: *"In two or three sentences, what would you tell someone who was about to trust this?"* This `final_critique` is the analog of `final_understanding` in solving. The coach compares it to `initial_critique` — the delta is the learning.

### Phase C4 — Wrap-Up

Same as Solving's wrap-up: thinking-trace summary, but framed around critique quality:
- *"You found N issues in this artifact. You retracted M of them after looking closer — that's calibration, not failure."*
- *"At first you said: '[initial_critique]'. After working through it: '[final_critique]'. That shift is the skill."*
- *"You missed [issue Z]. Worth knowing for next time — but you also caught [issue Y], which most people gloss over."*

### Constraints on the Critic-Coach (must be in its base prompt)

- **Never declare the artifact correct or incorrect overall.** Critique is per-claim; the synthesis is the student's call.
- **Never name an issue the student hasn't approached.** Coverage check is the only exception, and only as an open question.
- **Praise specifically.** "Good catch on the units" beats "great job." Teen calibration matters here.
- **Self-corrections are wins.** A retracted finding is the metacognitive skill firing correctly; reflect that warmly back.

---

## Specialization Plugin System

Each domain (math, programming, essay, science, etc.) is a **self-contained plugin** — a folder that registers its own system prompt, tools, and UI components. The core app has zero knowledge of any specific domain. Adding a new specialization requires no changes to core code.

### Plugin folder structure

All plugins live under `backend/specializations/`:

```
backend/specializations/
  math/
    __init__.py          ← registers the plugin
    prompt.txt           ← domain system prompt (Socratic core auto-prepended)
    tools/
      algebra.py         ← sympy CAS tool
      graph.py           ← matplotlib render tool
    manifest.json        ← declares tool names, descriptions, UI hints
  programming/
    __init__.py
    prompt.txt
    tools/
      code_runner.py
    manifest.json
  essay/
    __init__.py
    prompt.txt
    manifest.json        ← no tools in v1
  science/
    __init__.py
    prompt.txt
    tools/
      graph.py           ← shared impl (symlinked or copied from math/)
      data_table.py
    manifest.json
```

### manifest.json schema

```json
{
  "domain": "math",
  "display_name": "Mathematics",
  "complexity_hints": ["single-step", "multi-step", "open-ended"],
  "tools": [
    {
      "name": "algebra",
      "description": "Symbolic algebra and calculus via sympy",
      "endpoint": "/tools/algebra",
      "ui_component": "AlgebraSteps",
      "input_schema": {
        "expression": "string",
        "operation": "simplify | solve | diff | integrate"
      }
    },
    {
      "name": "graph",
      "description": "Plot a mathematical expression",
      "endpoint": "/tools/graph",
      "ui_component": "GraphView",
      "input_schema": {
        "expression": "string",
        "x_range": "[number, number]",
        "variables": "object"
      }
    }
  ],
  "ui_components": [
    {
      "name": "AlgebraSteps",
      "description": "Step-by-step rendering of symbolic manipulation output from the algebra tool.",
      "props_schema": {
        "steps": "Array<{ expr: string, rule: string }>",
        "final": "string"
      },
      "trigger": "tool_result"
    },
    {
      "name": "GraphView",
      "description": "Renders a plot from a backend-rendered PNG or inline SVG.",
      "props_schema": {
        "image_url": "string",
        "caption": "string?"
      },
      "trigger": "tool_result"
    },
    {
      "name": "RuleRecallPrompt",
      "description": "Inline card asking the student to state which rule applies before any algebraic step. Domain-specific Socratic widget.",
      "props_schema": {
        "candidate_rules": "string[]",
        "context_expr": "string"
      },
      "trigger": "agent_directive"
    }
  ]
}
```

`tools[].ui_component` and entries in `ui_components` must reference the **same name** the frontend exports from `frontend/src/specializations/<domain>/`. The frontend's `registry.ts` maps `"<domain>.<ComponentName>"` to a React component. Names not present in the registry cause the frontend to log a warning and render a fallback — the chat itself must still proceed.

`trigger` declares when a component appears:
- `tool_result` — rendered by `ToolPane` after a `/tools/{name}` call returns
- `agent_directive` — rendered inline (or in a side panel) when the agent emits a `ui_directive` in its `/chat` response (see "Specialization UI Contract")

### Plugin registration (Python)

```python
# backend/specializations/math/__init__.py
from app.plugin_registry import register_specialization

register_specialization(
    domain="math",
    prompt_file=__file__,           # resolved relative to this folder
    tools=["algebra", "graph"],
)
```

### Generic tool dispatch

All tool calls go through a single endpoint. The registry resolves the handler:

```
POST /tools/{tool_name}
  body: { session_id, ...tool-specific args }
  returns: { result, ui_component, display_data }
```

The LLM never calls a hardcoded endpoint. It picks from the tool list injected into its system prompt by the active plugin.

### Specialization UI Contract

A specialization can ask the frontend to render its own React components in two ways:

**1. Tool results** — when the agent calls a tool, the tool's response carries a `ui_component` name and a `display_data` payload. The frontend looks up `<domain>.<ui_component>` in `registry.ts` and renders it inside the `ToolPane`. This is the existing flow.

**2. Agent directives** — the agent can ask the frontend to render a domain-specific widget *without* a tool call, by emitting a `ui_directives` array in its `/chat` response. This is how specializations attach Socratic widgets (e.g. a "pick the rule that applies" card, a confidence slider tied to a concept, a pseudocode pad).

Extended `/chat` response shape:

```json
{
  "reply": "Before we simplify, which rule applies here?",
  "phase": "solving",
  "subproblems": [ ... ],
  "ui_directives": [
    {
      "component": "RuleRecallPrompt",
      "domain": "math",
      "props": {
        "candidate_rules": ["distributive", "associative", "commutative"],
        "context_expr": "3(x + 2)"
      },
      "placement": "inline | side_panel | modal",
      "lifetime": "until_dismissed | until_next_turn | persistent_in_subproblem"
    }
  ]
}
```

Rules:

- The agent **may not bypass the Socratic rules through UI** — a `RuleRecallPrompt` may surface candidate answers, but its props must not contain the correct answer, hint level, or completed work. Treat directives the same as chat text: they ask, they don't tell.
- The frontend treats `ui_directives` as advisory. If `component` isn't in the registry for that `domain`, log a warning and continue — the conversation must never break because a widget is missing.
- `placement: inline` renders inside `ChatPane` attached to the message. `side_panel` opens `ToolPane`. `modal` blocks the chat until dismissed (use sparingly; reserve for high-friction moments like the escape-hatch reflection gate).
- `lifetime` decides when the frontend removes the widget. `until_next_turn` is the default for transient prompts; `persistent_in_subproblem` for widgets that should stay alive while a subproblem is active.
- User interaction with a widget is sent back as the next `/chat` message — the body grows a `directive_response` field: `{ message?, directive_response?: { component, value } }`. The agent reads the value and continues the Socratic loop.

Backend prompt guidance for emitting directives lives in each domain's `prompt.txt`. The Socratic base prompt should remind the model: *"You may emit `ui_directives` to elicit structured input from the student, but never to deliver answers or hints beyond your current escalation level."*

### Adding a new specialization (checklist)

Backend half (`backend/specializations/{domain}/`):
1. Create the folder.
2. Write `prompt.txt` (Socratic rules auto-prepended). Include guidance on when to emit `ui_directives`.
3. Implement any tools in `tools/` (or reuse existing ones via import).
4. Write `manifest.json` — declare `tools` and the full `ui_components` catalog.
5. Register in `__init__.py`.

Frontend half (`frontend/src/specializations/{domain}/`):
6. Create the folder.
7. Implement one `.tsx` component per entry in the manifest's `ui_components` list, with the declared props shape.
8. Export them from a `index.ts` and add entries to `frontend/src/specializations/registry.ts` keyed `"<domain>.<ComponentName>"`.

The domain then appears automatically in detection, routing, and the `/specializations` discovery endpoint. No changes to `/chat`, `/session/new`, or any other specialization. If only the backend half is landed, the frontend renders a fallback when directives reference unknown components — work in progress is safe to merge.

---

## Domain System Prompts

Each specialization's `prompt.txt` extends the Socratic core (which is always prepended). The Socratic base enforces the universal rules (one question at a time, never enumerate subproblems, etc.).

### Mathematics (`backend/specializations/math/prompt.txt`)
```
You are a maths tutor. When the student needs to see symbolic work, invoke the
algebra tool — do not compute by hand in the chat. When a visual would help,
invoke the graph tool. Never simplify expressions for the student unless they
have attempted it first. Ask "what rule applies here?" before any algebraic step.
```

### Programming (`backend/specializations/programming/prompt.txt`)
```
You are a programming tutor. Do not write code for the student. Ask them to
write pseudocode first. When they have working pseudocode, help them translate
it. Use the code runner to test their implementations, then ask them to explain
the output. For bugs, ask "what do you expect this line to do?" before pointing
at the error.
```

### Essay / Writing (`backend/specializations/essay/prompt.txt`)
```
You are a writing coach. Do not draft any part of the essay for the student.
Help them build an outline by asking about their argument and evidence.
For each paragraph, ask "what is the one thing this paragraph must prove?"
```

### Science (`backend/specializations/science/prompt.txt`)
```
You are a science tutor. Ground every concept in an observable or experimental
basis. Ask the student "how would you test this?" for any claim. Use the graph
tool to plot data the student provides. Do not state laws or formulae — ask
the student to recall or derive them.
```

### General (`backend/specializations/general/prompt.txt`)
```
You are a Socratic tutor for general questions. Identify the core concept the
student is trying to understand. Ask them what they already know before
offering any framing. Use only questions and analogies — never definitions or
explanations offered unprompted.
```

---

## UI Components

### Always present
- **ChatPane** — the primary conversation surface, markdown-rendered, streaming

### Contextual (rendered when relevant)
- **SubproblemPanel** — decomposition tree, collapsible, status indicators
- **ToolPane** — slides in from right when a tool result is available
  - GraphView (iframe / img from backend render)
  - AlgebraSteps (step-by-step sympy output)
  - CodeOutput (terminal-style)
- **HintBadge** — subtle indicator on each subproblem node showing hint count
- **ConfidenceWidget** — 1–5 star selector, shown after each subproblem closes
- **CalibrationCheck** — 1–5 prediction asked *before* the student attempts a step (vs. ConfidenceWidget which fires after)
- **ReflectionPrompt** — inline card asking a metacognitive question; the response goes back as `directive_response` and is evaluated by the agent
- **CritiqueArtifactPanel** — shown in critique mode; renders the artifact under review
- **CritiqueFindingsList** — running list of issues the student has named, with `verified` state from coach probing
- **ThinkingTraceDrawer** — slides up at session end, shows narrative reflection

---

## Reflection & Calibration Subsystem

Two threads run alongside both loops. They are the product's most direct answer to the brief's "handle uncertainty" and "reflect on mistakes" targets.

### Periodic Reflection Prompts

The agent emits a `ReflectionPrompt` directive at four trigger points:

1. **Mid-session, periodic** — after every 2 closed subproblems (solving) or every 2 verified findings (critique). One question, calibrated to what just happened. Examples: *"What was different about how you approached sp-2 vs. sp-1?"* / *"You almost dropped that finding before catching it again — what made you take a second look?"*
2. **Self-correction follow-up** — when `control.self_correction_noted = true`, the *next* turn asks: *"What made you change your mind?"* Cheap, high-value moment.
3. **Escape hatch reflection** — the existing one-sentence gate before the answer is shown. Phase 3e of solving.
4. **Wrap-up reflection** — the synthesis question that produces `final_understanding` / `final_critique`.

Every reflection response is stored in `session.reflection_prompts` with the original question.

### Reflection Quality Evaluation

A reflection that says "I dunno, it just clicked" is less useful than one that says "I realized I was using the formula for X but the problem actually needed Y." The agent does a lightweight self-evaluation: on the turn *after* a reflection response, the agent sets `reflection_prompts[-1].quality` to `shallow | decent | deep` based on the response's content. If `shallow`, the agent follows up with one more probing question. **Maximum one follow-up per reflection** — no badgering.

This evaluation happens inside the same JSON output (`control.last_reflection_quality`), not as a separate LLM call.

### Calibration (Predict-then-Check)

Before the student attempts a subproblem (solving) or commits to a finding (critique), the agent may emit a `CalibrationCheck` directive: *"Before you try — how confident are you that you'll get this right? 1 to 5."* The student's answer is stored as a `calibration_point.predicted_confidence`. After the attempt resolves, the agent records the `outcome` (correct / wrong / partial) on the same point.

At wrap-up, the calibration trace becomes part of the thinking trace narrative:
- *"You predicted 4/5 confidence on three steps. You got two of them. Your gut is slightly ahead of your accuracy — worth noticing."*
- *"On the one you predicted 2/5, you actually nailed it. You knew more than you thought you did."*

Calibration is a v1 must-have, not a stretch goal: it's the only feature that directly trains uncertainty handling, which the brief calls out as a core target behaviour. The agent emits CalibrationCheck on at least one subproblem per session.

### Why these are in their own subsystem and not inside each loop

Solving and Critique both produce reflection prompts and calibration points. Keeping the subsystem orthogonal to mode means we can tune reflection frequency and evaluation strictness in one place rather than two prompts. The Socratic base prompt owns the contract; per-mode prompts only describe when to trigger, not how.

---

## Thinking Trace (formerly "session metrics")

> **Why this name matters**: This is not a performance score. It is a record of
> *how* the student thought — what they tried, where they got stuck, when they
> changed their mind. Framing it as a "trace" signals that the process is the
> point, not the answer.

Tracked automatically throughout the session. Shown as a reflection surface at wrap-up, never as a grade or score.

```json
{
  "mode": "solving | critique",
  "total_turns": 24,
  "phase_breakdown": { "clarification": 3, "decomposition": 5, "solving": 14, "wrap_up": 2 },
  "subproblems": [
    {
      "id": "sp-1",
      "description": "student's own words",
      "hints_used": 2,
      "direct_answer_requested": false,
      "escape_hatch_reflection": null,
      "confidence_score": 4
    }
  ],
  "critique_findings": [
    { "id": "f-1", "claim": "...", "kind": "factual_error", "verified": true, "was_self_corrected": false }
  ],
  "calibration_summary": {
    "points": [{ "predicted": 4, "outcome": "correct" }, { "predicted": 2, "outcome": "correct" }],
    "label": "well_calibrated | overconfident | underconfident | mixed",
    "evidence": "AI-generated 1-sentence summary of the pattern"
  },
  "reflection_summary": {
    "deep_reflections": 2,
    "decent_reflections": 1,
    "shallow_reflections": 0,
    "highlights": ["one or two of the deepest reflection quotes"]
  },
  "direct_answers_requested": 0,
  "self_corrections": 2,
  "initial_understanding": "I thought it was just about finding the roots",
  "final_understanding": "It's actually about the structure of the solution space",
  "understanding_delta_label": "significant | moderate | small",
  "understanding_delta_evidence": "AI-generated 1-sentence comparison of initial vs final",
  "initial_critique": null,
  "final_critique": null,
  "critique_delta_label": null,
  "critique_delta_evidence": null
}
```

`critique_findings`, `initial_critique`, `final_critique`, `critique_delta_*` are populated in critique mode. `subproblems`, `initial_understanding`, `final_understanding`, `understanding_delta_*` in solving mode. The other fields apply to both.

**Displayed to student as a narrative reflection, not a dashboard.** Solving mode:
- *"You broke the problem into N parts yourself and solved them in X turns."*
- *"You used hints on 2 of the 3 subproblems — on the third you got it without any."*
- *"At the start you said: '[initial_understanding]'. By the end you could explain: '[final_understanding]'. That shift is the learning."*
- *"You corrected your own thinking twice — noticing your own mistakes is a skill."*
- *"You predicted 4/5 confidence on three steps and got two — your gut is slightly ahead of your accuracy."*
- If escape hatch was used: *"On one step you asked for the answer directly. You wrote: '[escape_hatch_reflection]'. That moment of knowing you were stuck is worth remembering."*

Critique mode:
- *"You found N issues in this artifact. You retracted M of them after looking closer — that's calibration, not failure."*
- *"At first you said: '[initial_critique]'. After working through it: '[final_critique]'."*
- *"You missed [missed_issue]. Worth knowing — but you also caught [hardest_caught_issue], which most people gloss over."*

The understanding delta (solving) or critique delta (critique) is the most important output of the whole session. It is visible proof of thinking, not just task completion. This is the feature to demo in the pitch.

---

## API Endpoints

```
POST /session/new
  body: {
    username: string,                          // required
    mode: "solving" | "critique",              // required
    query?: string,                            // required for solving and for "generate" critique
    artifact?: { source: "imported", content: string }
             | { source: "generate", prompt: string },  // required for critique mode
  }
  returns: { session_id, mode, domain, artifact?, opening_message }
  note: classifier runs internally. For critique mode with source="generate",
        a separate LLM call (LLM_MODEL_ARTIFACT) produces the artifact before
        the critic-coach opens the session. Anonymous sessions are not supported.

POST /chat                                      [SSE]
  body: { session_id, message?: string, directive_response?: { component, value } }
  events:
    event: token   data: { delta: "..." }       // streamed chunks of reply
    event: state   data: { control: { ... } }   // emitted once at end; validated control object
    event: error   data: { code, message }      // if the agent's output failed validation; client retries
  note: either message or directive_response must be present. See "Specialization UI Contract"
        and the structured-output schemas in socratic_base.txt / critic_base.txt for the
        control shape (it differs by mode).

POST /tools/{tool_name}
  body: { session_id, ...tool-specific args }
  returns: { result, ui_component, display_data }
  note: tool_name must be registered in the active domain's manifest.json. Backend invokes
        these on the agent's behalf when control.tool_call is set; the result is replayed
        into the next turn's context. The frontend does not call this endpoint directly in v1.

GET /session/{session_id}/thinking-trace
  returns: { ...thinking trace object }
  note: shape varies by mode; see "Thinking Trace" section

POST /persona/create
  body: { username: string }
  returns: { status: "exists" | "pending", session_id?, persona? }
  note: on "pending", a short onboarding session_id is created; the frontend continues via
        /chat against the "persona" domain. On "exists", returns the stored persona.

POST /persona/reset
  body: { username: string }
  returns: { status: "reset" }

GET /specializations
  returns: [ { domain, display_name, tools: [], ui_components: [] } ]
  note: auto-generated from plugin registry. The frontend uses ui_components to validate
        that every component name has a matching entry in registry.ts at boot; missing
        names log a warning but do not block.
```

---

## LLM Prompt Construction (per turn)

```python
def build_prompt(session: Session, user_message: str) -> list[dict]:
    domain_prompt = plugin_registry.get_prompt(session.domain)  # loads specialization/prompt.txt
    persona_ctx = session.persona.to_context_str() if session.persona else ""
    return [
        {"role": "system", "content": SOCRATIC_BASE + "\n\n" + domain_prompt},
        {"role": "system", "content": f"Student profile:\n{persona_ctx}"},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
        {"role": "user", "content": user_message}
    ]
```

`SOCRATIC_BASE` is a constant string (defined in `backend/app/prompts/socratic_base.txt`) that enforces the universal rules: one question at a time, never enumerate subproblems, never give the full solution, tools produce data not answers, etc. It is always prepended before the domain prompt.

`session.to_context_str()` returns a compact JSON of current phase, active subproblem, hint count, and student's stated initial understanding.

The model to call is read from the `LLM_MODEL` environment variable and passed to OpenRouter. No model name is hardcoded anywhere in the application.

---

## Phase Transition Rules

```
clarification  →  decomposition   when: initial_understanding is captured
decomposition  →  solving         when: student confirms subproblem list
solving        →  solving         when: subproblem closes, next activates
solving        →  wrap_up         when: all subproblems are status=solved
```

Phase transitions are detected by the LLM (via a structured output call) or triggered explicitly by the student ("I think I've broken it down enough").

---

## Key Constraints (must be enforced in all system prompts)

1. **Never give the full solution.** Not even partially, unless the escape hatch is triggered.
2. **One question at a time.** Never ask two questions in the same message.
3. **Never enumerate subproblems.** Always ask the student to find them.
4. **Validate understanding before moving on.** Confidence check after each subproblem.
5. **Tools produce data, not answers.** Always ask the student to interpret tool output.
6. **Escape hatch is per-subproblem.** Giving away one step doesn't unlock the rest.

---

## Deployment

The product runs on the team's **AWS EC2 instance** (instance details in team channel, not in this repo).

### Topology

- One EC2 host runs both backend (FastAPI on port 8000) and frontend (static build served by nginx on port 80/443).
- Nginx is the public-facing entry: serves frontend static files, reverse-proxies `/api/*` to the FastAPI on 127.0.0.1:8000 (so SSE works without CORS gymnastics).
- HTTPS via Let's Encrypt (`certbot --nginx`). Re-uses the EC2 instance's public DNS or a team-provided subdomain.
- No load balancer, no autoscaling — this is a demo box.

### Process management

- Backend: `systemd` unit running `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`. Single worker because session state is in-memory; sticky sessions on multiple workers would need shared storage (out of scope for v1).
- Frontend: built into `frontend/dist/` at deploy time, served as static files. No node process in production.
- Logs to journald; `journalctl -u socratic-tutor` reads them.

### Env vars

- Backend: `LLM_MODEL_TUTOR`, `LLM_MODEL_CLASSIFIER`, `LLM_MODEL_ARTIFACT`, `OPENROUTER_API_KEY`, `PERSONA_DIR` (defaults to `backend/personas/`), `ALLOWED_ORIGINS` (CSV, defaults to the public hostname).
- Frontend: built with `VITE_API_URL=/api` and `VITE_USE_MOCK=false`. The frontend never talks directly to OpenRouter.

### Secrets

- `OPENROUTER_API_KEY` lives in `/etc/socratic-tutor.env` (`chmod 600`, owned by the service user). Read by the systemd unit via `EnvironmentFile=`. Never in the repo, never in a Docker image.

### Deploy steps (manual v1)

1. SSH to EC2.
2. `git pull` in the deploy directory.
3. Backend: `pip install -e ".[dev,math]"`, then `sudo systemctl restart socratic-tutor`.
4. Frontend: `npm install && npm run build`, then `sudo cp -r frontend/dist/* /var/www/socratic-tutor/`.
5. `sudo nginx -t && sudo systemctl reload nginx`.

A bash script under `deploy/deploy.sh` will wrap these once the first deploy lands. CI/CD is out of scope for v1.

### Persona files in production

`backend/personas/*.json` is the only on-disk state. It survives restarts because it's a regular directory, not a tmpfs. Back up periodically by snapshotting the directory (a daily `tar.gz` to `~/persona-backups/` via cron is fine for v1). If the host is rebuilt, persona files must be preserved out-of-band — they are the only thing in this system that can't be regenerated.

---

## What to Build First (MVP cut + stretch)

The MVP slice is the minimum that lets us demo the brief's "show and do, don't tell" + "judge AI outputs" thesis with one domain end-to-end. Ship MVP first; stretch items only after MVP is stable and deployed.

### MVP (must ship before demo)

1. **Plugin registry** — folder-scanning loader, manifest parser, tool dispatcher (`/tools/{tool_name}`)
2. **Socratic base prompt** — `backend/app/prompts/socratic_base.txt`, shared across all domains and modes
3. **Critic base prompt** — `backend/app/prompts/critic_base.txt`, used in critique mode
4. **Core chat loop** — FastAPI `/chat` (SSE) + OpenRouter relay + session state in memory + JSON schema validation of agent output
5. **Domain detection** — classifier call in `/session/new` via `LLM_MODEL_CLASSIFIER`
6. **First domain: math (school-level)** — algebra tool, plot tool, calibrated for ages 13–18 (linear equations, basic geometry, intro probability, NOT undergraduate)
7. **Solving phase state machine** — clarification → decomposition → solving → wrap-up; agent emits transitions, backend validates
8. **Critique mode** — artifact import + generated artifact path, phase machine (clarification → critique → synthesis → wrap-up), CritiqueArtifactPanel, CritiqueFindingsList
9. **Persona onboarding (short)** — 2-question intake via `"persona"` specialization, stub persona file, inline `persona_updates` capture during sessions
10. **SubproblemPanel + CritiqueArtifactPanel UI**
11. **Hint ladder + escape hatch with reflection gate** — tracked in session state, escalates in agent's system prompt context
12. **Reflection prompts** — periodic, self-correction follow-up, escape-hatch, wrap-up; with quality evaluation
13. **Calibration (predict-then-check)** — CalibrationCheck directive, calibration_points in session state, summary in thinking trace
14. **Specialization UI registry + ToolPane** — for tool_result and agent_directive component rendering
15. **Thinking trace + ThinkingTraceDrawer** — narrative with understanding delta (solving) or critique delta (critique) as centrepiece
16. **Deploy to EC2** — nginx + systemd + Let's Encrypt; manual deploy script

### Stretch (after MVP holds together)

17. **Second domain: programming (intro)** — Pseudocode pad, code runner (sandboxed), calibrated for first-time programmers
18. **Seeded-flaw artifacts** — Critique mode's generated artifacts get a secondary editing pass that inserts a subtle error, raising critique difficulty
19. **Essay, science, general specializations** — already scaffolded; flesh out prompts and any required tools

### Stop-the-line items

The following are blockers that must hold throughout MVP development, not features to add:

- **Agent Socratic discipline.** Every model output must be validated against the rules (never give the answer, one question at a time, etc.). Build a regression harness for this in `backend/tests/test_socratic_constraints.py` early — seeded dialogues + assertions on forbidden patterns. If the model drifts on a swap, this catches it.
- **Code runner sandbox.** Stretch item 17 ships only after sandboxing is real (subprocess + resource limits + read-only FS at minimum). No "TODO sandbox" in production code.

---

## Out of Scope (v1)

- User login with passwords / auth tokens
- Firebase / cloud storage (personas are local JSON files on the EC2 disk)
- Cross-session learning (persona accumulates inferred fields, but agent does not adapt strategy across sessions)
- Multi-user concurrency stress (single worker, in-memory sessions — fine for demo, not for class rollout)
- Persona editing UI
- Teacher / parent dashboards
- Mobile-optimised layout (responsive enough not to break, but desktop-first)

These are documented for v2 but should not influence v1 architecture decisions. Keep session state in-memory and stateless across restarts, except for persona files.
