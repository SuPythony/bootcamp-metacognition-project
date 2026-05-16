# Prompt Issues

Hub for all known prompt-level problems. Each item has a location (which file
to fix), a problem statement, and a concrete action. Engineering issues live
in `issues-and-changes.md` — this file is prompt-only.

---

## 1 — Core Socratic discipline

These are direct violations of the app's fundamental rules.

---

**P1.1 — Agent confirms answers directly**
`socratic_base.txt`

Agent says "That's exactly right!" before the student has verified. Student
never develops the habit of self-checking.

*Action:* Agent must never confirm a numerical or logical answer. Instead ask:
"Does that check out?" or "How would you verify that?" Confirmation only after
the student checks it themselves.

---

**P1.2 — Hollow praise openers**
`socratic_base.txt`

Every response begins with "Great!", "Excellent thinking!", "You've got a great
handle on that!" — content-free, patronising to teens, and obscures whether the
student actually got something right.

*Action:* Prohibit affirmative openers. Respond to the substance directly.
"You've got it" as a standalone confirmation is also banned — always follow with
a question or the next move.

---

**P1.3 — Repetitive variable definitions**
`socratic_base.txt`

Agent asks the student to define variables already established earlier in the
same session. In our test: u, a, t were defined for the velocity formula and
then re-requested for the displacement formula two turns later.

*Action:* Agent must track what has been established in the session context and
never re-ask for it. Instruction: "If the student has already defined or
demonstrated understanding of a concept or variable in this session, do not ask
them to re-define it. Reference it directly."

---

**P1.4 — No self-verification step**
`socratic_base.txt`

Related to P1.1. After any subproblem closes, the agent moves on without asking
the student to verify the result makes sense.

*Action:* After every subproblem resolution, one verification question before
closing: "Does that answer make sense in the context of the original problem?"
or "Is there a quick way to check that?"

---

## 2 — Student agency

The loop trains students to answer questions. It needs to also train them to
ask questions and frame problems.

---

**P2.1 — No problem-framing moment**
`socratic_base.txt`

Agent engages with the problem immediately. Students never practice the
upstream skill: is this the right problem, is it precisely stated?

*Action:* Before engaging with the problem, ask once: "Is this the right
problem to solve? Is there a sharper version of what you're trying to figure
out?" Record `original_query` and `refined_query` in session state.

---

**P2.2 — Agent always prompts the next move**
`socratic_base.txt`

Fully automated scaffolding suppresses self-regulation — the exact skill the
app targets. The student never has to self-initiate.

*Action:* For sessions with 2+ subproblems, activate one silently — no opening
question. If student doesn't engage within their turn, prompt once: "Over to
you." Nothing else.

---

**P2.3 — Student never formulates a question**
`socratic_base.txt` + domain prompts

The agent asks all questions; the student answers them. Real-world AI use
requires the opposite skill.

*Action:* Once per session at a mid-session transition: "You ask me one
question about this problem — not what you're stuck on, something that would
help you understand it more deeply." Log `student_question_quality: precise |
vague | surface`. If vague, one follow-up only: "Can you make that more
specific?"

---

**P2.4 — Agent doesn't notice or name disengagement**
`socratic_base.txt`

When the student opts out mentally ("I'd just google it", "just tell me"),
the agent ignores it and moves on. Missed metacognitive moment.

*Action:* When student signals disengagement, reflect it back with curiosity
before continuing: "What would you search for? What would you do with what
you found?" Not punitive — one question, then move on regardless of answer.

---

**P2.5 — Question quality variance**
Domain prompts (`math/`, `programming/`, `essay/`)

Domain prompts specify intent ("ask a conceptual question") but not form.
Results in repetitive or vague questions that frustrate students.

*Action:* Add concrete example questions at each of the five hint levels in
every domain prompt. These are quality anchors, not scripts. Also: regression
harness should flag the same question form used twice in a row on one
subproblem.

---

## 3 — Session structure

How the session flows and how subproblems are introduced.

---

**P3.1 — Subproblem split timing is broken**
`socratic_base.txt`

Two failure modes observed: (A) split happens too early, before the student
has engaged, without the student naming the parts themselves; (B) split never
happens even after many turns where the student is stuck and cannot proceed.

*Action:* Agent must not introduce a subproblem breakdown until the student
has made at least one genuine attempt at the problem. If after several turns
the student is still unable to proceed, the agent introduces the decomposition
step explicitly: "Let's break this down — what do you think the first smaller
piece of this problem is?" This is the agent recognising the student is stuck,
not the agent pre-empting.

---

**P3.2 — Subproblem split not communicated**
`socratic_base.txt`

When the agent does split the problem into subproblems, it sometimes does so
silently in the UI without telling the student what just happened or why.

*Action:* Whenever subproblems are created, the agent must narrate the split:
"I've noted those two parts — we'll tackle them one at a time. Which feels
more approachable to start with?"

---

## 4 — High-friction moments

---

**P4.1 — Escape hatch reflection comes before the answer**
`socratic_base.txt`

Current design: reflection required before showing the answer. This is the
highest-friction possible sequencing — student is most frustrated and hits
a gate. Real-world data shows students abandon the tool at this moment.

*Action:* Give the answer first, then ask: "While it's fresh — in one
sentence, where exactly did your thinking get stuck?" Same data captured,
abandonment risk drops.

---

**P4.2 — Calibration miss has no handling**
`socratic_base.txt`

When a student's outcome doesn't match their predicted confidence, the agent
treats it as a neutral event. Students who discover they're overconfident
disengage from metacognitive strategies.

*Action:* Explicit instruction for calibration miss: "You called that a 4 and
hit some friction — that gap is useful. What felt different from what you
expected?" One question. Do not dwell.

---

## 5 — Tool use

---

**P5.1 — Tools not called when expected**
Domain prompts (`math/`, `science/`)

Agent works through calculations in chat instead of invoking the algebra or
graph tool. Student loses the visual/verification benefit, and the agent is
effectively doing the work itself.

*Action:* Domain prompts must be explicit about when tools are mandatory, not
optional. For math: "Any symbolic manipulation beyond substituting a single
value must use the algebra tool, not chat." For graph: "Whenever a function
over a range is discussed, invoke the graph tool before asking the student to
reason about its shape."

---

**P5.2 — Student input can trigger unintended tool behavior**
`socratic_base.txt` + domain prompts

Student typing tool-like phrases ("can sympy do this", "call the function X")
causes the agent to treat these as legitimate tool requests or ask clarifying
questions as if they were. Students can cause unintended behaviors without
intending to.

*Action:* Agent must only invoke tools it has registered in the current domain
manifest. Any student reference to an unrecognized tool name should be ignored
and redirected: "I can only use [available tools] for this problem — let's
work with those. What were you hoping to see?"

---

**P5.3 — No graceful degradation message when tool fails**
`socratic_base.txt`

When a tool call fails (wrong domain, tool not registered), the agent silently
continues asking for inputs as if the tool is about to be called. Student
sees the error but gets no acknowledgment.

*Action:* When a tool call fails, agent must acknowledge it explicitly and
pivot: "The graph tool isn't available here — let's reason through the shape
without it. What would you expect the curve to look like?"

---

## 6 — Classifier

---

**P6.1 — Physics problems classified as `science` instead of `math`**
Classifier prompt

Physics word problems (kinematics, projectile motion, forces) are routed to
the `science` specialization, which has no algebra or graph tools registered.
Both tools silently fail for the entire session.

*Action:* Update classifier prompt to explicitly route physics calculation
problems to `math`. Instruction: "Problems involving equations, numerical
calculation, or symbolic manipulation — including physics problems — should
be classified as `math` unless they are purely conceptual or experimental."

---

## 7 — Schema upgrades required

Some prompt fixes cannot be enforced by prompt wording alone — they require
new fields in the control object or session state so the agent can track and
expose the relevant information. Listed here by which prompt issue they
support.

---

### 7.1 — Session state additions

These live on the `Session` object (server-side), not in the per-turn control
output. They persist across turns.

```json
"original_query": "string — what the student typed at session start",
"refined_query": "string | null — sharpened version from P2.1 framing moment",
"established_concepts": ["list of variable names / concepts the student has
                          already defined this session — prevents P1.3 re-asking"],
"decomposition_source": "student | agent | null — who introduced the breakdown
                          (supports P3.1 tracking)"
```

`established_concepts` is updated by the agent via a new `control` field (see
below). The backend merges it into session state each turn.

---

### 7.2 — Control object additions

These are emitted by the agent in the per-turn JSON output and validated by
the backend.

```json
"control": {
  ...existing fields...,

  "refined_query": "string | null",
  // Set once during clarification if the student sharpens the problem (P2.1).
  // Backend writes this to session state. Null if problem accepted as-is.

  "concepts_established": ["x", "velocity", "..."],
  // Any variable or concept the student demonstrated understanding of this
  // turn. Backend appends to session.established_concepts (P1.3).

  "student_question_quality": "precise | vague | surface | null",
  // Set during the student-asks moment (P2.3). Null all other turns.

  "decomposition_source": "student | agent | null",
  // Set when subproblems are first created. Tracks whether the student
  // named the parts or the agent introduced them (P3.1, P3.2).

  "disengagement_noted": false,
  // True when agent detects student opting out mentally (P2.4).
  // Triggers the redirect question; recorded in thinking trace.

  "verification_requested": false
  // True when agent asked student to verify their answer before closing
  // a subproblem (P1.4). Regression harness checks this fires at least
  // once per solved subproblem.
}
```

---

### 7.3 — Thinking trace additions

These surface in the wrap-up `ThinkingTraceDrawer` and the
`GET /session/{id}/thinking-trace` response.

```json
"original_query": "string",
"refined_query": "string | null",
// Shows the student whether they sharpened the problem (P2.1 delta).

"student_questions": [
  { "question": "string", "quality": "precise | vague | surface" }
],
// One entry per student-asks moment (P2.3). Surfaced in trace as:
// "You asked: '...' — that kind of question is the real skill."

"decomposition_source": "student | agent",
// Surfaced as: "You identified the structure of this problem yourself"
// vs "We broke this down together."

"disengagement_count": 0
// Number of turns where disengagement was noted. Not shown to student
// directly — informs the calibration summary narrative.
```

---

### 7.4 — Validation rules to add to backend

These should be checked in the Pydantic schema or the post-parse validator,
not just relied on from the prompt:

- `hint_level` must be exactly `previous_hint_level + 1` or `0` on a new
  subproblem — no jumping (already in spec, verify it is actually enforced)
- `tool_call.name` must be in the registered tool list for the active domain —
  reject unknown tool names with a parse error, not silently (P5.2)
- `verification_requested` must be `true` at least once before any subproblem
  `status` transitions to `"solved"` — enforces P1.4 at the schema level
- `decomposition_source` must be set when `subproblem_updates` first
  populates — cannot be null once subproblems exist

---

## Summary

| ID | Location | Urgency |
|---|---|---|
| P1.1 | `socratic_base.txt` | High |
| P1.2 | `socratic_base.txt` | High |
| P1.3 | `socratic_base.txt` | High |
| P1.4 | `socratic_base.txt` | Medium |
| P2.1 | `socratic_base.txt` | Medium |
| P2.2 | `socratic_base.txt` | Medium |
| P2.3 | `socratic_base.txt` + domain prompts | Medium |
| P2.4 | `socratic_base.txt` | Low |
| P2.5 | Domain prompts | Medium |
| P3.1 | `socratic_base.txt` | High |
| P3.2 | `socratic_base.txt` | Medium |
| P4.1 | `socratic_base.txt` | High |
| P4.2 | `socratic_base.txt` | Medium |
| P5.1 | Domain prompts | High |
| P5.2 | `socratic_base.txt` + domain prompts | Medium |
| P5.3 | `socratic_base.txt` | Medium |
| P6.1 | Classifier prompt | High |
| P7 (schema) | `session.py`, `chat.py`, Pydantic schema | High for 7.4; Medium for 7.1–7.3 |

| ID | Location | Urgency |
|---|---|---|
| P1.1 | `socratic_base.txt` | High |
| P1.2 | `socratic_base.txt` | High |
| P1.3 | `socratic_base.txt` | High |
| P1.4 | `socratic_base.txt` | Medium |
| P2.1 | `socratic_base.txt` | Medium |
| P2.2 | `socratic_base.txt` | Medium |
| P2.3 | `socratic_base.txt` + domain prompts | Medium |
| P2.4 | `socratic_base.txt` | Low |
| P2.5 | Domain prompts | Medium |
| P3.1 | `socratic_base.txt` | High |
| P3.2 | `socratic_base.txt` | Medium |
| P4.1 | `socratic_base.txt` | High |
| P4.2 | `socratic_base.txt` | Medium |
| P5.1 | Domain prompts | High |
| P5.2 | `socratic_base.txt` + domain prompts | Medium |
| P5.3 | `socratic_base.txt` | Medium |
| P6.1 | Classifier prompt | High |