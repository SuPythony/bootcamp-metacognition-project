# Socratic Tutor

> **The AI never solves the problem. It guides the student to solve it themselves.**

A web-based learning tool for teenagers (roughly 13–18) that strengthens thinking skills which stay valuable in an AI-rich world: framing problems, checking understanding, calibrating confidence, reflecting on mistakes, and judging AI outputs.

Built for the [Metacognition Vibe Coding Task](https://docs.tk.sg/Metacognition-Vibe-Coding-Task-551dd9d8b64483d7942101e280188fdb).

---

## Design thesis

In an AI-rich world, the ability to frame problems, judge outputs, and monitor one's own thinking matters more, not less. Every feature of this app should strengthen one of those behaviours — not shortcut it. Students learn by doing: through decision-making, decomposition, and reflection. Never by reading tips or watching the AI perform.

---

## What it does

The product is one loop in v1, with a second loop designed and deferred:

**Solving Mode (v1)** — The student brings a school-level problem (algebra, intro programming, essay outline). A Socratic tutor agent guides them to construct the solution themselves, never giving the answer.

**Critique Mode (v1.1, designed)** — The student brings an AI-generated artifact and a Critic-Coach guides them to evaluate it. This is the "judge AI outputs" axis the brief calls for.

Both modes share the same infrastructure from day one. Adding Critique Mode in v1.1 is additive, not disruptive.

---

## The Solving Loop

Every session moves through four phases:

```
Clarification → Decomposition → Solving → Wrap-Up
```

**Clarification** — The AI does not engage with the problem until the student has stated their own understanding first. Even "I have no idea" is valid; the point is to anchor a starting position to compare against at the end.

**Decomposition** — The AI never lists the subproblems. It nudges the student to find them. The `SubproblemPanel` builds the decomposition tree live as the student proposes parts.

**Solving (per subproblem)** — For each subproblem, the agent uses an escalating hint ladder (five levels, from conceptual question to near-direct nudge). Tools (algebra CAS, graph, code runner) produce data for the student to interpret — never answers. An escape hatch allows a student to request a direct answer after genuine stuck-ness, but requires a one-sentence reflection first.

**Wrap-Up** — The student synthesises the full solution in their own words. Their current explanation is compared against their `initial_understanding`. The delta is the most important output of the session.

### Reflection & Calibration

Two threads run across the whole loop:

- **Calibration (predict-then-check):** Before attempting a subproblem, the student predicts their confidence (1–5). After the attempt resolves, the outcome is recorded. The thinking trace at wrap-up shows the student their accuracy pattern.
- **Periodic reflection prompts:** The agent asks a metacognitive question after every two closed subproblems, after self-corrections, at the escape hatch gate, and at wrap-up. Each response is quality-evaluated by the agent (shallow / decent / deep); shallow responses get one follow-up question.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind + TypeScript |
| Backend | Python + FastAPI |
| LLM routing | OpenRouter (model-agnostic; set via `LLM_MODEL_TUTOR` env var) |
| Streaming | Server-Sent Events on `/chat` |
| Tool execution | Backend (sympy, matplotlib) + browser-side (Pyodide for Python) |
| Session state | In-memory, server-side |
| Persona persistence | JSON files on disk (`backend/personas/`) |
| Deployment | AWS EC2, nginx reverse proxy, systemd, Let's Encrypt |

---

## Architecture

```
Browser (React + Vite, port 5173)
  │  HTTP / SSE
  ▼
FastAPI (port 8000, single worker)
  ├── /session/new    — domain detection via classifier model
  ├── /chat           — SSE relay, session state, JSON schema validation
  ├── /tools/{name}   — generic tool dispatch (backend tools)
  └── /specializations — plugin discovery
  │
  ▼
Specialization plugins (backend/specializations/)
  ├── math        — algebra (sympy), graph (matplotlib)
  ├── programming — code_runner (Pyodide, browser-side)
  ├── essay       — prompt-only, no tools
  └── persona     — reserved for onboarding, never user-selectable
  │
  ▼
OpenRouter → configured model via LLM_MODEL_TUTOR env var
```

Frontend and backend are independent projects. Their only coupling is HTTP. The frontend runs fully standalone against an in-browser mock (`VITE_USE_MOCK=true`).

---

## Specialization plugin system

Each domain is a self-contained plugin: a folder under `backend/specializations/` that declares its own system prompt, tools, and UI components via `manifest.json`. The core app has zero knowledge of any specific domain. Adding a new specialization requires no changes to core code.

Every specialization is a pair: a backend half (prompt, tools, manifest) and a frontend half (React components). They are coupled only by names declared in `manifest.json`'s `ui_components` list.

---

## Persona & onboarding

Students identify by username (no password). On first visit, a two-turn onboarding captures age band and initial intent. From that point, the persona grows passively: the agent infers education level, confident/difficult subjects, and learning style from conversation, flagging inferred fields as hypotheses rather than facts.

Persona files are the only on-disk state. They survive server restarts and must be backed up before any instance rebuild.

---

## Getting started

### Backend

```bash
cd backend
pip install -e ".[dev,math]"

# copy and fill env vars
cp .env.example .env

uvicorn app.main:app --reload   # port 8000
```

Required env vars: `LLM_MODEL_TUTOR`, `LLM_MODEL_CLASSIFIER`, `OPENROUTER_API_KEY`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env

npm run dev          # port 5173
npm run typecheck    # type check
```

Set `VITE_USE_MOCK=true` to run fully in-browser without the backend.

### Tests

```bash
cd backend
pytest
pytest tests/test_socratic_constraints.py   # regression harness for Socratic rules
```

---

## Deployment (AWS EC2)

1. SSH to instance
2. `git pull`
3. Backend: `pip install -e ".[dev,math]"` → `sudo systemctl restart socratic-tutor`
4. Frontend: `npm install && npm run build` → `sudo cp -r frontend/dist/* /var/www/socratic-tutor/`
5. `sudo nginx -t && sudo systemctl reload nginx`

HTTPS via Let's Encrypt. `OPENROUTER_API_KEY` in `/etc/socratic-tutor.env` (`chmod 600`), never in the repo.

---

## Demo guide (for the team)

### What to show

The product's thesis is that a student's thinking improves over repeated sessions — not just within one. This means **a single cold-start demo will not show the metacognitive gains the product is designed to build.** Research on Socratic AI tutoring systems (SocraticAI, arXiv 2512.03501) shows the observable skill shift — from vague help-seeking to structured problem decomposition — emerges over 2–3 weeks of use, not in one session.

**Design the demo around a trajectory, not a session.**

### Recommended demo structure

1. **Run two sessions with the same username before the demo.** Use a prepared math or programming problem. Let the first session be rough — the student gets stuck, uses hints, maybe the escape hatch. Let the second session be cleaner. Save both sessions.

2. **Open with the Thinking Trace from session 1.** Walk through the calibration summary, the reflection quality breakdown, and the understanding delta. Show the raw `initial_understanding` vs `final_understanding` text side by side. This is the centrepiece — it's visible proof of thinking, not just task completion.

3. **Then show a live session (session 3) on a fresh problem.** The audience can see the decomposition tree building live, the hint ladder escalating, the escape hatch flow if needed.

4. **Close by reopening the Thinking Trace from session 3 and comparing it to session 1.** The shift in how the student articulates their understanding — even across a short demo period — is the argument.

### What to watch for in live sessions

- The decomposition phase is the highest-risk moment: if the agent accidentally lists subproblems rather than asking for them, the Socratic discipline breaks visibly. Have the regression test harness output ready to show the constraint is enforced.
- Calibration moments land best when the student gets one prediction wrong. Don't script a perfect session — a calibration miss that the student reflects on is more compelling than flawless performance.
- The escape hatch, if triggered, is not a failure state. The one-sentence reflection it captures is one of the most powerful moments in the product. Let it happen naturally.

### What not to demo

- Don't demo the programming domain without first confirming Pyodide has fully loaded (~10 MB, first load). Open the programming domain in a browser tab 5 minutes before the demo to warm it up.
- Don't demo a username that hasn't had at least one prior session. The persona-informed tutor behaviour is noticeably different from a blank onboarding session.

---

## Current state

The repository is fully scaffolded with stubs. See `CLAUDE.md` for the complete spec.

**Real and frozen:** directory layout, manifest schemas, API contract, `socratic_base.txt` (v1), `critic_base.txt` (v1.1 draft)

**Stubs:** FastAPI routes return placeholders; React components render placeholders; tool modules raise `NotImplementedError`; plugin registry loader not yet wired

**Build order:** Plugin registry → `/chat` SSE relay → math end-to-end → prompt regression harness → programming (Pyodide) + essay → reflection/calibration → persona onboarding → deploy → (v1.1) Critique Mode

---

## Out of scope (v1)

Auth tokens, cloud storage, cross-session learning adaptation, multi-user concurrency at scale, persona editing UI, teacher dashboards, mobile-first layout.