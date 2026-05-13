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

A chat-first teaching assistant that:
1. Identifies the query domain (math, programming, essay writing, science, etc.)
2. Routes to a domain-specific system prompt and UI
3. Walks the student through a structured **Socratic solving loop**
4. Offloads mechanical sub-tasks (algebra, graphing, code execution) to backend tools
5. Tracks session-level metrics on the student's problem-solving process

**Current scope (v1)**: Solving loop + session metrics. Simple username-based persona persistence. No Firebase, no auth tokens.

---

## Login & Persona Flow

On first launch (or if no persona file exists for the user), the app runs a **one-time onboarding conversation** before routing to the main tutor. The persona is then saved to disk and reattached on every subsequent session — no re-asking.

### Onboarding flow

1. User enters a username (no password — this is identity, not auth).
2. App checks `personas/{username}.json`. If it exists → skip to session.
3. If not: start the **persona interview** — an LLM-driven conversational intake.
4. After the interview, an LLM call synthesises responses into a structured persona file and saves it.
5. Session begins with persona attached to the system prompt.

### Persona interview (LLM-driven)

The intake is a short conversation, not a form. The LLM asks 5–8 questions, one at a time:

```
System: You are conducting a brief background intake for an AI tutoring app.
Ask the student 5–8 questions, one at a time, to understand:
- Their current educational level (school year, university, self-taught, etc.)
- Subjects they feel confident in
- Subjects they find difficult
- How they prefer to learn (examples first, theory first, trial-and-error, etc.)
- Any specific goals for using this tutor
Do NOT ask for personal details. Keep each question short and conversational.
When done, output ONLY a JSON object (no preamble) with the schema below.
```

### Persona JSON schema (`personas/{username}.json`)

```json
{
  "username": "alex",
  "created_at": "2025-01-01T00:00:00Z",
  "education_level": "undergraduate | high_school | self_taught | professional | other",
  "education_detail": "2nd year computer science",
  "confident_subjects": ["linear algebra", "Python"],
  "difficult_subjects": ["probability", "recursion"],
  "learning_style": "examples_first | theory_first | trial_and_error | mixed",
  "goals": "Prepare for algorithms exam in 3 weeks",
  "preferred_pace": "slow | medium | fast",
  "raw_responses": [
    { "question": "...", "answer": "..." }
  ]
}
```

`raw_responses` is kept for potential future reprocessing; only the structured fields are used in the system prompt.

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

- Personas stored as JSON files in `personas/` directory (server-side).
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

```
Browser (React)
  │
  ├── ChatPane            ← primary interaction surface
  ├── SubproblemPanel     ← decomposition tree, built collaboratively
  ├── ToolPane            ← renders tool output for whichever specialization is active
  └── MetricsDrawer       ← session summary (shown at end)
        │
        ▼
FastAPI backend
  ├── POST /chat              ← main message relay, carries session state
  ├── POST /session/new       ← initialise session, detect domain
  ├── POST /tools/{tool_name} ← generic tool dispatch (routes to registered plugins)
  └── GET  /session/metrics   ← return session summary object
        │
        ▼
Specialization Plugin Registry
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
  "domain": "mathematics | programming | essay | science | general",
  "original_query": "...",
  "phase": "clarification | decomposition | solving | wrap_up",
  "initial_understanding": "student's articulated understanding (captured in clarification phase)",
  "subproblems": [
    {
      "id": "sp-1",
      "description": "...",
      "goal": "what the student says this part should achieve",
      "status": "pending | active | solved",
      "hints_given": 0,
      "direct_answer_requested": false
    }
  ],
  "active_subproblem_index": 0,
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

---

## The Solving Loop (CRITICAL — core of the product)

This is the heart of the app. Every design decision should serve this flow.

### Phase 0 — Domain Detection (automatic, 1 LLM call)

On the first user message, a fast classification call determines:
- `domain`: mathematics | programming | essay | science | general
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

## Specialization Plugin System

Each domain (math, programming, essay, science, etc.) is a **self-contained plugin** — a folder that registers its own system prompt, tools, and UI components. The core app has zero knowledge of any specific domain. Adding a new specialization requires no changes to core code.

### Plugin folder structure

```
specializations/
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
  ]
}
```

### Plugin registration (Python)

```python
# specializations/math/__init__.py
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

### Adding a new specialization (checklist)

1. Create `specializations/{domain}/`
2. Write `prompt.txt` (Socratic rules are auto-prepended)
3. Implement any tools in `tools/` (or reuse existing ones via import)
4. Write `manifest.json`
5. Register in `__init__.py`
6. Restart — the domain appears automatically in detection and routing

No changes to `/chat`, `/session/new`, the frontend, or any other specialization.

---

## Domain System Prompts

Each specialization's `prompt.txt` extends the Socratic core (which is always prepended). The Socratic base enforces the universal rules (one question at a time, never enumerate subproblems, etc.).

### Mathematics (`specializations/math/prompt.txt`)
```
You are a maths tutor. When the student needs to see symbolic work, invoke the
algebra tool — do not compute by hand in the chat. When a visual would help,
invoke the graph tool. Never simplify expressions for the student unless they
have attempted it first. Ask "what rule applies here?" before any algebraic step.
```

### Programming (`specializations/programming/prompt.txt`)
```
You are a programming tutor. Do not write code for the student. Ask them to
write pseudocode first. When they have working pseudocode, help them translate
it. Use the code runner to test their implementations, then ask them to explain
the output. For bugs, ask "what do you expect this line to do?" before pointing
at the error.
```

### Essay / Writing (`specializations/essay/prompt.txt`)
```
You are a writing coach. Do not draft any part of the essay for the student.
Help them build an outline by asking about their argument and evidence.
For each paragraph, ask "what is the one thing this paragraph must prove?"
```

### Science (`specializations/science/prompt.txt`)
```
You are a science tutor. Ground every concept in an observable or experimental
basis. Ask the student "how would you test this?" for any claim. Use the graph
tool to plot data the student provides. Do not state laws or formulae — ask
the student to recall or derive them.
```

### General (`specializations/general/prompt.txt`)
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
- **ThinkingTraceDrawer** — slides up at session end, shows narrative reflection

---

## Thinking Trace (formerly "session metrics")

> **Why this name matters**: This is not a performance score. It is a record of
> *how* the student thought — what they tried, where they got stuck, when they
> changed their mind. Framing it as a "trace" signals that the process is the
> point, not the answer.

Tracked automatically throughout the session. Shown as a reflection surface at wrap-up, never as a grade or score.

```json
{
  "total_turns": 24,
  "phase_breakdown": {
    "clarification": 3,
    "decomposition": 5,
    "solving": 14,
    "wrap_up": 2
  },
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
  "direct_answers_requested": 0,
  "self_corrections": 2,
  "initial_understanding": "I thought it was just about finding the roots",
  "final_understanding": "It's actually about the structure of the solution space",
  "understanding_delta_label": "significant | moderate | small",
  "understanding_delta_evidence": "AI-generated 1-sentence comparison of initial vs final"
}
```

**Displayed to student as a narrative reflection, not a dashboard:**
- *"You broke the problem into N parts yourself and solved them in X turns."*
- *"You used hints on 2 of the 3 subproblems — on the third you got it without any."*
- *"At the start you said: '[initial_understanding]'. By the end you could explain: '[final_understanding]'. That shift is the learning."*
- *"You corrected your own thinking twice — noticing your own mistakes is a skill."*
- If escape hatch was used: *"On one step you asked for the answer directly. You wrote: '[escape_hatch_reflection]'. That moment of knowing you were stuck is worth remembering."*

The understanding delta between `initial_understanding` and `final_understanding` is the most important output of the whole session. It is visible proof of thinking, not just task completion. This is the feature to demo in the pitch.

---

## API Endpoints

```
POST /session/new
  body: { query: string, username?: string }
  returns: { session_id, domain, opening_message }

POST /chat
  body: { session_id, message: string }
  returns: { reply, phase, subproblems, tool_calls: [] }

POST /tools/{tool_name}
  body: { session_id, ...tool-specific args }
  returns: { result, ui_component, display_data }
  note: tool_name must be registered in the active domain's manifest.json

GET /session/{session_id}/thinking-trace
  returns: { ...thinking trace object }

POST /persona/create
  body: { username: string }
  returns: { status: "exists" | "created", persona }
  note: if persona doesn't exist, triggers LLM onboarding interview

POST /persona/reset
  body: { username: string }
  returns: { status: "reset" }

GET /specializations
  returns: [ { domain, display_name, tools: [] } ]
  note: auto-generated from plugin registry — useful for frontend and debugging
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

`SOCRATIC_BASE` is a constant string (defined in `app/prompts/socratic_base.txt`) that enforces the universal rules: one question at a time, never enumerate subproblems, never give the full solution, tools produce data not answers, etc. It is always prepended before the domain prompt.

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

## What to Build First (Recommended Order)

1. **Plugin registry** — folder-scanning loader, manifest parser, tool dispatcher (`/tools/{tool_name}`)
2. **Socratic base prompt** — `app/prompts/socratic_base.txt`, shared across all domains
3. **Core chat loop** — FastAPI `/chat` + OpenRouter relay + session state in memory
4. **Domain detection** — simple classification prompt, returns domain enum; validated against registered plugins
5. **First specialization (math)** — algebra + graph tools, as a reference implementation for the plugin pattern
6. **Remaining specializations** — programming, essay, science, general (each as a plugin)
7. **Phase state machine** — clarification → decomposition → solving → wrap-up
8. **Persona onboarding** — LLM-driven interview, `personas/{username}.json` persistence, `/persona/create` + `/persona/reset`
9. **Persona injection** — attach to system prompt on session start
10. **SubproblemPanel UI** — renders decomposition tree, updates live
11. **Hint ladder** — tracked in session state, escalates in system prompt context
12. **ToolPane UI** — slides in when tool result available; `ui_component` field in tool response drives which view renders
13. **Confidence widget** — post-subproblem check-in
14. **Thinking trace + ThinkingTraceDrawer** — session narrative at wrap-up, understanding delta as centrepiece
15. **Escape hatch with reflection gate** — confirmed twice, reflection sentence required before answer is given

---

## Out of Scope (v1)

- User login with passwords / auth tokens
- Firebase / cloud storage (personas are local JSON files)
- Cross-session learning (persona is static once created; no session-to-session updates)
- Age/experience adaptation beyond what the persona provides
- Real-time persona updates mid-session

These are documented for v2 but should not influence v1 architecture decisions. Keep session state in-memory and stateless across restarts, except for persona files.
