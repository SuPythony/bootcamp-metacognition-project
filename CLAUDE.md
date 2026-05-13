# CLAUDE.md — Socratic Tutor App

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

**Current scope (v1)**: Solving loop + session metrics. No login, no Firebase, no persistent user profiles.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind |
| Backend | Python + FastAPI |
| LLM routing | OpenRouter (Claude Sonnet as primary) |
| Tool execution | FastAPI endpoints (algebra CAS, code runner, graphing) |
| Session state | In-memory (server-side, keyed by session ID) |
| Auth | None (v1) |

---

## Architecture

```
Browser (React)
  │
  ├── ChatPane            ← primary interaction surface
  ├── SubproblemPanel     ← decomposition tree, built collaboratively
  ├── ToolPane            ← graphs / code output / algebra steps (contextual)
  └── MetricsDrawer       ← session summary (shown at end)
        │
        ▼
FastAPI backend
  ├── POST /chat              ← main message relay, carries session state
  ├── POST /session/new       ← initialise session, detect domain
  ├── POST /tools/graph       ← matplotlib / plotly render → base64
  ├── POST /tools/algebra     ← sympy CAS
  ├── POST /tools/run-code    ← sandboxed exec (Python / JS)
  └── GET  /session/metrics   ← return session summary object
        │
        ▼
OpenRouter  →  Claude Sonnet (teaching persona)
              (tool calls invoke FastAPI tool endpoints)
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

## Domain System Prompts

Each domain gets a base system prompt that extends the Socratic core.

### Mathematics
```
You are a maths tutor. When the student needs to see symbolic work, invoke the
algebra tool — do not compute by hand in the chat. When a visual would help,
invoke the graph tool. Never simplify expressions for the student unless they
have attempted it first. Ask "what rule applies here?" before any algebraic step.
```

### Programming
```
You are a programming tutor. Do not write code for the student. Ask them to
write pseudocode first. When they have working pseudocode, help them translate
it. Use the code runner to test their implementations, then ask them to explain
the output. For bugs, ask "what do you expect this line to do?" before pointing
at the error.
```

### Essay / Writing
```
You are a writing coach. Do not draft any part of the essay for the student.
Help them build an outline by asking about their argument and evidence.
For each paragraph, ask "what is the one thing this paragraph must prove?"
```

### Science
```
You are a science tutor. Ground every concept in an observable or experimental
basis. Ask the student "how would you test this?" for any claim. Use the graph
tool to plot data the student provides. Do not state laws or formulae — ask
the student to recall or derive them.
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
  body: { query: string }
  returns: { session_id, domain, opening_message }

POST /chat
  body: { session_id, message: string }
  returns: { reply, phase, subproblems, tool_calls: [] }

POST /tools/algebra
  body: { expression: string, operation: "simplify"|"solve"|"diff"|"integrate" }
  returns: { steps: [], result: string }

POST /tools/graph
  body: { expression: string, x_range: [number, number], variables: {} }
  returns: { image_base64: string }

POST /tools/run-code
  body: { code: string, language: "python"|"javascript" }
  returns: { stdout: string, stderr: string, error: bool }

GET /session/{session_id}/thinking-trace
  returns: { ...thinking trace object }
```

---

## LLM Prompt Construction (per turn)

```python
def build_prompt(session: Session, user_message: str) -> list[dict]:
    return [
        {"role": "system", "content": DOMAIN_SYSTEM_PROMPTS[session.domain] + SOCRATIC_BASE},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
        {"role": "user", "content": user_message}
    ]
```

`session.to_context_str()` returns a compact JSON of current phase, active subproblem, hint count, and student's stated initial understanding.

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

1. **Core chat loop** — FastAPI `/chat` + OpenRouter relay + session state in memory
2. **Domain detection** — simple classification prompt, returns domain enum
3. **Socratic system prompts** — one per domain, tested manually
4. **Phase state machine** — clarification → decomposition → solving → wrap-up
5. **SubproblemPanel UI** — renders decomposition tree, updates live
6. **Hint ladder** — tracked in session state, escalates in system prompt context
7. **Tool endpoints** — algebra (sympy), graph (matplotlib), code runner (subprocess/sandbox)
8. **ToolPane UI** — slides in when tool result available
9. **Confidence widget** — post-subproblem check-in
10. **Thinking trace + ThinkingTraceDrawer** — session narrative at wrap-up, understanding delta as centrepiece
11. **Escape hatch with reflection gate** — confirmed twice, reflection sentence required before answer is given

---

## Out of Scope (v1)

- User login / accounts
- Firebase / persistent storage
- Cross-session memory / user personas
- Age/experience adaptation
- AI-generated persona JSON from background questions

These are documented for v2 but should not influence v1 architecture decisions. Keep session state in-memory and stateless across restarts.
