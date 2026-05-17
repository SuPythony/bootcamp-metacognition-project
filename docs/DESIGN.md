# Aporeka — Product Design

This document covers the full product design: pedagogical framework, solving loop, critique loop, specialization plugin system, session schema, and the reflection/calibration subsystem. It is the source of truth for product decisions — consult it when adding features or modifying prompts.

For API shapes see [API.md](API.md). For deployment see [DEPLOY.md](DEPLOY.md). For engineering issues and roadmap see [ISSUES.md](../ISSUES.md) and [PLAN.md](../PLAN.md).

---

## Design thesis

In an AI-rich world, the ability to frame problems, judge outputs, and monitor one's own thinking matters more, not less. Every feature of this app should strengthen one of those behaviours — not shortcut it. Students learn by doing: through decision-making, decomposition, and reflection. Never by reading tips or watching the AI perform.

---

## Project overview

A web-based learning tool for **teenagers (roughly 13–18)** that strengthens thinking skills which stay valuable in an AI-rich world: framing problems, checking understanding, calibrating confidence, reflecting on mistakes, and **judging AI outputs**. Built for the [Metacognition Vibe Coding Task](https://docs.tk.sg/Metacognition-Vibe-Coding-Task-551dd9d8b64483d7942101e280188fdb).

**v1 scope**: Solving Mode only. Three core specializations: math (school-level algebra + graphing), programming (intro Python + Pyodide runner), essay (argumentation, no tools). Science and general are scaffolded.

**v1.1**: Critique Mode — student brings an AI artifact and the Critic-Coach guides them to evaluate it. Design is retained below and in `critic_base.txt`; architecture is built to make this additive.

---

## Pedagogical framework

Aporeka grounds its design in two frameworks that reinforce each other.

**Pólya's four steps** map directly to the four session phases:
- Clarification → Understand the problem (model misconceptions before asking)
- Decomposition → Devise a plan (student finds the structure)
- Solving → Carry it out (hint ladder + Pólya heuristics at level 3)
- Wrap-up → Look back (surface the understanding delta)

**Socratic dialogue** is the interaction mode throughout: the tutor only asks questions. It never names subproblems, confirms answers directly, or writes the next step.

The two frameworks keep the session from drifting into explanation or correction — the two most common failure modes for AI tutoring systems.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind + TypeScript |
| Backend | Python + FastAPI |
| LLM routing | OpenRouter (model-agnostic; set via `LLM_MODEL_TUTOR` env var) |
| Streaming | Server-Sent Events on `/chat` (stub — currently full JSON; see ISSUES.md #6) |
| Tool execution | Backend (sympy, matplotlib) + browser-side (Pyodide for Python) |
| Session state | In-memory, server-side |
| Persona persistence | JSON files on disk (`backend/personas/`) |

---

## Architecture

```
Browser (React + Vite, port 5173)
  │  HTTP / SSE
  ▼
FastAPI (port 8000, single worker)
  ├── /session/new    — domain detection via classifier model
  ├── /chat           — session state machine, JSON schema validation
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

## Login & Persona Flow

**Design intent**: get the student into a productive session as fast as possible. Onboarding asks the minimum; the rest of the persona is **inferred passively** from conversation.

### Onboarding flow (v1)

1. User enters a username (no password — identity, not auth).
2. `/persona/create` checks `backend/personas/{username}.json`. If it exists → `status: "exists"` → skip to session.
3. If new: `status: "confirm_new"` (without `confirm=true`) — frontend shows inline confirmation to prevent typo-driven accounts.
4. With `confirm=true`: `status: "pending"` → a 2-turn onboarding session runs via `/chat` against the reserved `"persona"` domain:
   - Turn 1: age / school year
   - Turn 2: initial intent
5. The persona agent emits `wrap_up` → frontend routes back to onboarding Step 2 (enter the problem).
6. From that session onward, every `/chat` response may include `signal.persona_updates` that merges into the persona file (inferred fields flagged `inferred: true`).

### Persona JSON schema

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

Fields set at onboarding (`age_band`, `school_level`, `initial_intent`) are flat strings. Every inferred field is `{ value, inferred, evidence? }` so the agent treats inferred signals as hypotheses.

`testuser.json` is pre-created and committed — skip onboarding during local dev.

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
  "initial_understanding": "student's articulated understanding (captured at clarification exit)",
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
    { "id": "f-1", "claim": "...", "kind": "factual_error | reasoning_gap | missing_step | overconfident_language | other", "verified": false }
  ],
  "calibration_points": [
    { "subproblem_id": "sp-1", "predicted_confidence": 4, "outcome": "correct | wrong | partial", "noted_at": "iso8601" }
  ],
  "reflection_prompts": [
    { "trigger": "periodic | self_correction | escape_hatch | wrap_up", "question": "...", "response": "...", "quality": "shallow | decent | deep | null" }
  ],
  "metrics": {
    "turns_total": 0,
    "hints_per_subproblem": [],
    "direct_answer_requests": 0,
    "self_corrections": 0,
    "phase_timestamps": {}
  }
}
```

`mode` is fixed at `/session/new`. `artifact` is only populated in critique mode. `critique_findings` are issues the student names; `verified` flips when the critic-coach confirms the issue is real after Socratic probing.

---

## Phase Transition Rules

```
clarification  →  decomposition   when: initial_understanding is captured (deterministic backend capture)
decomposition  →  solving         when: student confirms subproblem list
solving        →  solving         when: subproblem closes, next activates
solving        →  wrap_up         when: all subproblems are status=solved
```

Phase transitions are driven by the LLM's `control.phase` field. Illegal transitions (e.g. `clarification → wrap_up`) are clamped to the current phase with a warning log — never crash the conversation. `_apply_agent_response` does not touch `session.phase`; the caller (`_finalize_turn`) owns transitions.

---

## The Solving Loop

Every session moves through four phases.

### Phase 0 — Domain Detection (automatic, 1 LLM call)

On `/session/new`, a fast classification call via `LLM_MODEL_CLASSIFIER` determines:
- `domain`: math | programming | essay | science | general
- `complexity_hint`: single-step | multi-step | open-ended

The `persona` specialization is reserved for onboarding only — never returned by the classifier.

### Phase 1 — Clarification

**Rule**: The AI does NOT engage with the problem until the student has stated their own understanding.

The agent uses `thinking` to model likely misconceptions before writing any `reply`. Heuristic language must not appear in the reply.

Exit condition: Student has articulated some initial understanding (even "I have no idea where to start" is valid). `_maybe_capture_initial_understanding` fires deterministically on the clarification → next-phase transition; it does NOT rely on any agent signal.

### Phase 2 — Collaborative Decomposition

**Rule**: The AI never lists the subproblems. It nudges the student to identify them.

The `SubproblemPanel` renders the decomposition tree live as the student proposes parts. Each node shows: description, goal, status.

Exit condition: Student confirms the decomposition (or AI gently suggests they may be missing a key piece via a question, never a statement).

### Phase 3 — Solving Loop (per subproblem)

**3a. Activation** — AI asks the student to attempt the active subproblem.

**3b. Hint Ladder**

| Hint Level | Style |
|---|---|
| 0 | Precondition check (student hasn't shown any attempt) |
| 1 | Conceptual question (*"What does X mean in this context?"*) |
| 2 | Reframe (*"What if you thought about it as…?"*) |
| 3 | Pólya heuristic (working backward, simpler problem, analogy, specialisation, pattern) matched to the student's stuck-ness type |
| 4 | Worked analogy (*"Here's a similar but simpler case — does this help?"*) |
| 5 | Near-direct (*"You're very close. The key insight is [vague direction]."*) |

`hint_level: null` in a signal is a no-op (does not touch `hints_given`).

**3c. Tool Offload** — when mechanical sub-tasks require:
- Algebra / symbolic manipulation → `/tools/algebra` (sympy), show in ToolPane
- Graphing → `/tools/graph`, render in ToolPane, student interprets
- Code execution → `code_runner` tool (Pyodide, browser-side), show in `CodeOutput`, student interprets

The AI never presents tool output as "the answer." It presents it as data for the student to reason about.

**3d. Confidence Check** — after each subproblem, ask: *"How confident are you in this solution? 1–5?"*

**3e. Soft Escape Hatch** — if the student explicitly requests the answer after genuine stuck-ness:
1. *"I can tell you're stuck. Do you want a strong hint, or do you want me to just show you this step?"*
2. If they confirm "just show me": ask one sentence first — *"Before I show you — in one sentence, where exactly did your thinking get stuck?"* Store as `escape_hatch_reflection`.
3. Provide the answer for *that subproblem only* and continue. Never skip the reflection step.

### Phase 4 — Wrap-Up

After all subproblems are solved:
1. AI asks the student to synthesize: *"Can you now explain the full solution in your own words?"*
2. Agent emits `emit_reflection: "wrap_up"` → backend injects a `ReflectionPrompt` directive. Student answers.
3. Agent evaluates quality via `last_reflection_quality`. Backend sets `wrap_up_complete=true` on `ChatResponse` when the quality arrives (or when wrap_up is entered without a pending reflection).
4. Frontend transitions to `WrapUpView` only on `wrap_up_complete=true` — not on `phase="wrap_up"`.
5. `_maybe_run_wrap_up_summarizer` fires once at the first wrap_up turn, producing `final_understanding` + delta.

---

## The Critique Loop (v1.1 — design retained)

Same Socratic discipline as Solving, inverted: the AI produces or imports the content; the student evaluates it. Phase sequence: `clarification → critique → synthesis → wrap_up`.

### Setup

An `artifact` (worked AI solution, essay paragraph, code snippet) arrives by import (student pastes) or generation (backend calls `LLM_MODEL_ARTIFACT` with a non-Socratic prompt). Stored in `session.artifact`, displayed in `CritiqueArtifactPanel`.

### Phase C0 — Initial Read

Student provides `initial_critique` (one sentence gut feel). This anchors the wrap-up comparison.

### Phase C2 — Critique (per finding)

1. Student names an issue → becomes a `critique_finding`.
2. Coach probes: *"Walk me through where you see that."* / *"What would you expect to see if this part were correct?"* Never confirms or denies on the spot.
3. Student either strengthens (verified=true) or retracts the finding (a self-correction — celebrated).
4. Tool offload for math/code claims: algebra tool / code runner produces data; student interprets.
5. After student says they're done, one coverage check: *"Anything in this artifact you didn't look at carefully?"* (Only as a question, never as a statement.)

### Phase C3 — Synthesis

Student writes final verdict: *"In two or three sentences, what would you tell someone about to trust this?"* Stored as `final_critique`; delta vs. `initial_critique` is the learning.

### Critic-Coach constraints

- Never declare the artifact correct or incorrect overall.
- Never name an issue the student hasn't approached (coverage check is the only exception, and only as a question).
- Self-corrections are wins — celebrate them explicitly.

---

## Reflection & Calibration Subsystem

Two threads run across both loops. They are the product's most direct answer to the brief's "handle uncertainty" and "reflect on mistakes" targets.

### Reflection Prompts

The agent emits `signal.emit_reflection: "trigger_type"` at four points:

1. **periodic** — after every 2 closed subproblems / 2 verified findings.
2. **self_correction** — when `signal.self_correction_noted: true`, the next turn asks: *"What made you change your mind?"*
3. **escape_hatch** — the one-sentence gate before the answer is shown.
4. **wrap_up** — the synthesis question that produces `final_understanding`.

Backend selects a question from `REFLECTION_QUESTIONS[trigger_type]` (defined in `chat.py`) and injects a `ReflectionPrompt` directive. The model never generates the question text — it only names the trigger type. Question is chosen once in `_apply_agent_response` and reused in `_build_chat_response` via `session.pending_reflection_index`. De-duplication within a session prevents the same question appearing twice.

**XOR rule**: when `emit_reflection` is set, `parsed.reply` is set to `None` by `_finalize_turn`. The student sees the directive card, not chat text alongside it.

### Reflection Quality

On the turn after a reflection response, the agent sets `signal.last_reflection_quality: "shallow | decent | deep"`. If shallow, the agent follows up with one more probing question (maximum one follow-up per reflection).

### Calibration (Predict-then-Check)

Agent emits `signal.emit_calibration_check: true` → backend injects a `CalibrationCheck` directive: *"Before you try — how confident are you that you'll get this right? 1 to 5."* Stored as `calibration_point.predicted_confidence`. Later the agent emits `signal.calibration_outcome: "correct | wrong | partial"` to complete the point.

**XOR rule**: when `emit_calibration_check` is true, `parsed.reply` is set to `None`.

**Phase guard**: if `emit_calibration_check` is true and `control.phase == "wrap_up"` on the same turn, the phase transition is blocked.

`_compute_calibration_summary` at wrap-up derives a `well_calibrated | overconfident | underconfident | mixed` label from all session calibration points.

---

## Thinking Trace

The thinking trace is not a performance score — it is a record of *how* the student thought. Shown at session end as a narrative reflection, never a grade.

```json
{
  "mode": "solving | critique",
  "total_turns": 24,
  "phase_breakdown": { "clarification": 3, "decomposition": 5, "solving": 14, "wrap_up": 2 },
  "subproblems": [
    { "id": "sp-1", "description": "...", "hints_used": 2, "direct_answer_requested": false, "escape_hatch_reflection": null, "confidence_score": 4 }
  ],
  "calibration_summary": {
    "points": [{ "predicted": 4, "outcome": "correct" }],
    "label": "well_calibrated | overconfident | underconfident | mixed",
    "evidence": "one-sentence summary of the calibration pattern"
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
  "understanding_delta_evidence": "one-sentence comparison of initial vs final",
  "initial_critique": null,
  "final_critique": null,
  "critique_delta_label": null,
  "critique_delta_evidence": null
}
```

`initial_understanding` and `final_understanding` are populated by backend LLM summariser calls (not agent signals). `understanding_delta_label` and `understanding_delta_evidence` are computed at wrap-up by `_maybe_run_wrap_up_summarizer`.

---

## Specialization Plugin System

Each domain is a self-contained plugin: a folder under `backend/specializations/` with its own system prompt, tools, and UI components declared in `manifest.json`. The core app has zero knowledge of any specific domain.

### Plugin folder structure

```
backend/specializations/
  math/
    __init__.py       ← registers the plugin
    prompt.txt        ← domain system prompt
    tools/
      algebra.py      ← sympy CAS tool
      graph.py        ← matplotlib render tool
    manifest.json
  programming/
    __init__.py
    prompt.txt
    manifest.json     ← code_runner is frontend (Pyodide); no backend tool files
  essay/
    __init__.py
    prompt.txt
    manifest.json     ← no tools in v1
  science/
    __init__.py
    prompt.txt
    tools/
      graph.py        ← delegates to math graph
      data_table.py
    manifest.json
```

### manifest.json schema

```json
{
  "domain": "math",
  "display_name": "Mathematics",
  "tools": [
    {
      "name": "algebra",
      "description": "Symbolic algebra via sympy",
      "execution": "backend",
      "endpoint": "/tools/algebra",
      "ui_component": "AlgebraSteps",
      "input_schema": { "expression": "string", "operation": "simplify | solve | diff | integrate" }
    },
    {
      "name": "code_runner",
      "description": "Run a Python snippet in the browser via Pyodide",
      "execution": "frontend",
      "frontend_handler": "PyodideRunner",
      "ui_component": "CodeOutput",
      "input_schema": { "code": "string", "stdin": "string?" }
    }
  ],
  "ui_components": [
    {
      "name": "AlgebraSteps",
      "description": "Step-by-step rendering of sympy output",
      "props_schema": { "steps": "Array<{ expr: string, rule: string }>", "final": "string" },
      "trigger": "tool_result"
    },
    {
      "name": "RuleRecallPrompt",
      "description": "Inline card asking the student to state which rule applies",
      "props_schema": { "candidate_rules": "string[]", "context_expr": "string" },
      "trigger": "agent_directive"
    }
  ]
}
```

`trigger: "tool_result"` — rendered by `ToolPane` after a tool call returns.
`trigger: "agent_directive"` — rendered inline when the agent emits a `ui_directives` entry.

Frontend tools (`execution: "frontend"`) are dispatched by the browser. The agent emits `tool_call` as usual; the backend recognises `execution: "frontend"` and forwards via an SSE `frontend_tool` event. The frontend calls the `frontend_handler`, then POST the result back via `tool_result` in the `/chat` body.

### Agent directives (inline components)

The agent can ask the frontend to render a specialization-specific widget without a tool call by emitting `control.ui_directives`:

```json
[{
  "component": "RuleRecallPrompt",
  "domain": "math",
  "props": { "candidate_rules": ["distributive", "associative"], "context_expr": "3(x + 2)" },
  "placement": "inline | side_panel | modal",
  "lifetime": "until_dismissed | until_next_turn | persistent_in_subproblem"
}]
```

Rules:
- Directives may not contain the correct answer or completed work. They ask; they don't tell.
- If `component` isn't in the registry for that domain, log a warning and continue — the chat must never break because a widget is missing.
- User interaction with a widget is sent back via `directive_response: { component, value }` in the next `/chat` body.

### Adding a new specialization (checklist)

Backend (`backend/specializations/{domain}/`):
1. Create folder. Write `prompt.txt` and `manifest.json`. Implement backend tools in `tools/` if needed. Register in `__init__.py`.

Frontend (`frontend/src/specializations/{domain}/`):
2. Implement one `.tsx` component per `ui_components` entry. For frontend tools, implement the handler under `handlers/` and register in `registry.ts`. Export from `index.ts`, add entries to `registry.ts` keyed `"<domain>.<ComponentName>"`.

The domain appears automatically in detection, routing, and `/specializations`. No changes to core code.

---

## Domain System Prompts

Each specialization's `prompt.txt` extends the Socratic core (which is always prepended via the split prompt assembly). The Socratic base enforces universal rules; domain prompts add domain-specific constraints.

- **Math** — invoke the algebra tool for symbolic work, the graph tool for visuals; ask *"what rule applies here?"* before any algebraic step.
- **Programming** — ask for pseudocode first; use the code runner to test student implementations; ask *"what do you expect this line to do?"* for bugs.
- **Essay** — build the outline collaboratively; ask *"what is the one thing this paragraph must prove?"* for each paragraph; never draft.
- **Science** — ground every concept in an observable/experimental basis; ask *"how would you test this?"* for any claim; never state laws or formulae unprompted.
- **General** — identify the core concept; ask what the student already knows before offering any framing; use only questions and analogies.

---

## Prompt Architecture

The base prompt is assembled per-turn from a folder of files, not a single flat file.

### Folder layout (`backend/app/prompts/v1/`)

| File | When included |
|---|---|
| `core.txt` | Always. Universal Socratic rules, constraints 1–8, structured output contract, math formatting. |
| `phase_clarification.txt` | `session.phase == "clarification"` |
| `phase_decomposition.txt` | `session.phase == "decomposition"` |
| `phase_solving.txt` | `session.phase == "solving"` |
| `phase_wrap_up.txt` | `session.phase == "wrap_up"` |
| `block_tool_result.txt` | When the `/chat` request carried a `tool_result` field |
| `block_calibration.txt` | When an open `CalibrationPoint` exists |
| `block_reflection_eval.txt` | When a pending reflection has a student response but no quality evaluation |

Domain prompt (`backend/specializations/{domain}/prompt.txt`) is concatenated after the assembled base.

### Assembly

`load_base_prompt(variant_key, session, had_tool_result)` in `variants.py` reads `core.txt`, then conditionally appends phase and context blocks based on live session state. `chat.py` calls it every turn with the live `Session` object.

### LLM Prompt Construction (per turn)

```python
from app.prompts.variants import load_combined

def build_prompt(session: Session, user_message: str) -> list[dict]:
    domain_prompt = load_combined(
        session.domain,
        base_variant=_VARIANT_BASE,
        domain_variant=_VARIANT_DOMAIN_MAP.get(session.domain),
    )
    persona_ctx = session.persona.to_context_str() if session.persona else ""
    return [
        {"role": "system", "content": domain_prompt},
        {"role": "system", "content": f"Student profile:\n{persona_ctx}"},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
        {"role": "user", "content": user_message}
    ]
```

### Pólya roles across phases

- **Clarification** — use `thinking` to model likely misconceptions before writing `reply`. Heuristic language must not appear in `reply`.
- **Decomposition** — shapes questions implicitly; the student names the structure.
- **Solving** — level-3 hints draw on Pólya heuristics matched to the student's stuck-ness type.
- **Wrap-up** — drives synthesis and surfaces the delta between `initial_understanding` and current articulation.

### Prompt variants

Variant selection is static per server process — restart to switch.

```bash
PROMPT_VARIANT_BASE=base:v2 .venv/bin/python -m uvicorn app.main:app ...
PROMPT_VARIANT_DOMAIN=math:v2,essay:v1 .venv/bin/python -m uvicorn app.main:app ...
```

`VARIANTS` in `variants.py` maps string keys to `Path` objects. Old keys stay registered so historical probe runs remain reproducible. `parse_domain_variants(env_value)` raises `ValueError` at startup on malformed entries (missing `:`).

---

## Key Constraints (must be enforced in all system prompts)

1. **Never give the full solution.** Not even partially, unless the escape hatch is triggered.
2. **One question at a time.** Never ask two questions in the same message.
3. **Never enumerate subproblems.** Always ask the student to find them.
4. **Validate understanding before moving on.** Confidence check after each subproblem.
5. **Tools produce data, not answers.** Always ask the student to interpret tool output.
6. **Escape hatch is per-subproblem.** Giving away one step doesn't unlock the rest.

---

## UI Components catalogue

**Always present**
- `ChatPane` — primary conversation surface, markdown + LaTeX rendered

**Contextual**
- `SubproblemPanel` — decomposition tree, collapsible, status indicators, hint count
- `ToolPane` — slides in from right on tool result
  - `AlgebraSteps` — step-by-step sympy output
  - `GraphView` — backend-rendered PNG
  - `CodeOutput` — terminal-style Pyodide output
  - `DataTable` — tabular data from science tools
- `CalibrationCheck` — 1–5 prediction asked *before* the student attempts a step
- `ReflectionPrompt` — inline card asking a metacognitive question; response goes back via `directive_response`
- `ThinkingTraceDrawer` — slides up at session end; contains `TraceHero` (understanding diptych + delta), `TraceReflections` (reflection history cards), calibration summary
- `HintBadge` — subtle hint-count indicator on subproblem nodes
- `ConfidenceWidget` — 1–5 selector after each subproblem closes
- `CritiqueArtifactPanel` *(v1.1)* — artifact display
- `CritiqueFindingsList` *(v1.1)* — student-identified issues with `verified` state
