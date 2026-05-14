# Known Issues & Recommended Changes

Four items. The first is a code fix. The rest are prompt-only. Each action is the minimum change needed.

---

### 1 — Two backend fixes needed before demo

**History truncation:** A normal session hits 35–50 turns. The spec defers this to v2; it will break mid-demo. Fix in `build_prompt()`: sliding window of N most recent turns (N = 30), keeping the full system context and the pinned original problem statement. One function.

**Blocking tool calls:** sympy and matplotlib are synchronous and CPU-bound. Called directly inside `async def` handlers, they freeze the entire event loop while running. Wrap every call in `tools/algebra.py` and `tools/graph.py` with `asyncio.to_thread()` before wiring any tool into `/tools/{tool_name}`.

---

### 2 — The student is too passive; the agent speaks too freely

The loop trains students to answer well-posed questions. Real-world AI use requires the opposite: framing the problem first, then asking precise questions of the tool. Fully automated scaffolding also suppresses the self-regulation the app is trying to build — the agent prompting every move removes the need to self-initiate.

Four prompt-only changes to `socratic_base.txt` and domain prompts:

**Problem-framing (session start):** Before engaging with the problem, ask once: *"Is this the right problem to solve? Is there a sharper version of what you're trying to figure out?"* Record `original_query` and `refined_query` in session state.

**Agent silence (once per session):** For sessions with 2+ subproblems, activate one silently — wait for the student to self-initiate. If nothing comes, prompt once: *"Over to you."* Nothing else.

**Student asks (once per session):** At a mid-session transition: *"You ask me one question about this problem — not what you're stuck on, something that would help you understand it more deeply."* Log `student_question_quality: precise | vague | surface`. If vague, one follow-up: *"Can you make that more specific?"* Surface the quote in the thinking trace.

**Question templates:** Domain prompts specify intent but not form. Add concrete example questions at each of the five hint levels as quality anchors. Example for math level 1: *"What does the equals sign actually mean here? / What are you solving for — a value, or a relationship? / What would change if the coefficient were 1?"* Regression harness should flag the same question form repeated twice in a row on one subproblem.

---

### 3 — High-friction moments need reframing, not more gates

When students are most likely to abandon the tool, the current design adds friction. The escape hatch requires a reflection *before* the answer. A calibration miss gets no handling. Both cause disengagement at exactly the wrong moment.

Two prompt-only changes to `socratic_base.txt`:

**Escape hatch:** Give the answer first, then ask: *"While it's fresh — in one sentence, where exactly did your thinking get stuck?"* Same data, lower abandonment risk.

**Calibration miss:** Do not treat a wrong prediction as a mistake. Instead: *"You called that a 4 and hit some friction — that gap is useful. What felt different from what you expected?"* One question. Do not dwell.

---

### 4 — The demo should show both teaching loops

Solving Mode answers the brief partially: practise doing the task yourself. Critique Mode answers it more directly: practise evaluating what AI produces. Deferring Critique Mode to v1.1 is sound; leaving it invisible in the demo is not.

Show a static walkthrough of one Critique Mode session alongside the live demo — screenshots or a short clip. `critic_base.txt` is written; the architecture supports it. Frame explicitly: Solving Mode builds the infrastructure; Critique Mode is where it gets used on the problem the brief is actually asking about.

---

## Summary

| # | What | When | Effort |
|---|---|---|---|
| 1 | History truncation + async tool calls | Before demo | Low — two code changes |
| 2 | Student agency: problem-framing, silent subproblem, student-asks, question templates | Before prompts finalised | Zero code — prompt only |
| 3 | Friction moments: escape hatch reorder + calibration miss | Before prompts finalised | Zero code — prompt only |
| 4 | Demo strategy: show both loops | Before demo | Zero code — demo prep |