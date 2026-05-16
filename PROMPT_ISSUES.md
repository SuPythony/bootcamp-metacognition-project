# Prompt Issues

Hub for all known prompt-level problems. Open and partial items at the top.
Resolved items at the bottom for reference.

Status: 🔴 Open | ⚠️ Partial | ✅ Fixed

---

## Open & Partial

---

**P11.1 🔴 — Math probe: tutor prefers conceptual hint over tool invocation**
`math/prompt.txt` (TOOL SEQUENCING)

Probe: `math_tool_before_answer`. Student says
*"I moved the 3 to the right so I have 2x = 4. Now what? Just tell me x."*

Expected: `control.tool_call` invokes the algebra tool (the student has done one
mechanical step and is asking for the final mechanical step — exactly the
sequencing trigger).
Got: a Level 1 conceptual question (*"what's the opposite of multiplying by 2?"*)
with `tool_call: null`.

The reply is Socratically valid, but the rule the probe asserts — invoke the
algebra tool before any direct-answer pressure can land — is being skipped in
favour of conceptual scaffolding. Bias is correct *most* of the time; the
specific "student has done step 1, asks for step 2 outright" trigger is what
goes missing.

*Action:* In `math/prompt.txt` TOOL SEQUENCING, add an explicit anchor: "When
the student has completed at least one mechanical step AND requests the next
mechanical step directly, the next action is `tool_call: algebra`, not another
conceptual question." Validate via the `math_tool_before_answer` probe.

---

**P11.2 🔴 — Essay probe: counter-argument engagement phrasing too narrow**
Assertion (not prompt) — `tests/probes.py` `assert_reply_contains_any`

Probe: `essay_counter_argument_engaged`. Student dismisses the counter-argument
with *"that doesn't really matter."* The agent reply *"If you were arguing for
the other side, **why would** you say that connection is actually more
important…"* engages the counter-argument exactly as intended — but the
assertion checks for the literal strings `["what would", "why does",
"how would"]` and `"why would"` is not in the list.

This is half assertion-strictness, half prompt drift (the prompt could nudge
toward "what would they say" framings more consistently).

*Action:* Either (a) broaden `assert_reply_contains_any(["what would",
"why would", "why does", "how would"])` to include the modal `why would`, or
(b) tighten `essay/prompt.txt` counter-argument language to a canonical
phrasing the assertion expects. (a) is the lower-cost fix and semantically
correct — `"why would"` *is* genuine engagement.

---

**P6.1 🔴 — Physics problems classified as `science` instead of `math`**
Classifier prompt

Physics word problems (kinematics, forces, energy) routed to `science`,
which has no algebra or graph tools. Both tools silently fail.

*Action:* Update classifier prompt: "Problems involving equations,
calculation, or symbolic manipulation — including physics and chemistry
calculation problems — should be classified as `math` unless they are
purely conceptual or experimental."

---

**P7.4 ⚠️ — Backend validation rules not enforced**
`session.py`, `chat.py`

Documented in schema; not yet enforced in code:
- hint_level jump guard (no skipping levels)
- tool_call.name domain validation (reject unregistered tool names)
- verification_prompted required before subproblem close
- decomposition_source required when subproblems first created by tutor

---

## Resolved

| What | Fixed in |
|---|---|
| Agent confirms answers directly | `core.txt` Constraint 7 |
| Hollow praise openers | `core.txt` TONE |
| Repetitive variable/concept re-asking | `core.txt` Constraint 8 + `signal.concepts_established` |
| No self-verification before subproblem close | `core.txt` Constraint 5 + `signal.verification_prompted` |
| No problem-framing moment in clarification | `phase_clarification.txt` Step 2 + `signal.refined_query` |
| Agent always prompts next move | `phase_solving.txt` STUDENT AGENCY MOMENTS |
| Student never formulates a question | `phase_solving.txt` hand-control moment |
| Disengagement not noticed | `core.txt` TONE + `signal.disengagement_noted` |
| Subproblem split not communicated | `phase_decomposition.txt` CLOSING DECOMPOSITION |
| Escape hatch reflection before answer | `phase_solving.txt` ESCAPE HATCH: answer first |
| Student input triggers unregistered tools | Domain files: redirect to listed tools only |
| No graceful degradation on tool failure | Domain files: acknowledge and continue |
| Schema fields missing | `core.txt` new `signal` block |
| Math hint ladder anchors missing | `math/prompt.txt` HINT LADDER |
| Tool sequencing ambiguity | `math/prompt.txt` TOOL SEQUENCING |
| P2.5 — Question quality variance | Domain hint ladders: per-level anchors with heuristic labels |
| P3.1 — Subproblem split too early (failure mode A) | `phase_decomposition.txt` MINIMUM ENGAGEMENT RULE |
| P4.2 — Calibration miss has no in-session handling | `block_calibration.txt` CALIBRATION MISS section |
| P8.1 — Hint ladder precondition not enforced | `phase_solving.txt` Level 0 + precondition note |
| P8.2 / P5.1 — Post-graph question advisory | `block_tool_result.txt` mandatory one-question rule |
| P9.1 — Clarification without modelling misconceptions | `phase_clarification.txt` Step 1 (`thinking` only) |
| P9.2 — Pólya heuristics not embedded | `core.txt` PEDAGOGICAL FRAMEWORK (phase-role + selection logic); domain hint ladders (per-level heuristic labels); phase file headers |
| P9.3 — Wrap-up session ends before reflection response | `phase_wrapup.txt` explicit wait instruction |
| P10.1 — Student states answer without showing reasoning | `phase_solving.txt` STUDENT STATES ANSWER section |
| Agent intervenes when student is mid-reasoning | `core.txt` TONE (leave them alone); thinking scaffold |
| Heuristic selection was mechanical / flat list | `core.txt` PEDAGOGICAL FRAMEWORK: block-type matching, no reuse, phase gating |
| Adaptive tool invocation not specified | `core.txt` TOOL INVOCATION (three-tier); `math/prompt.txt` TOOL SEQUENCING; `programming/prompt.txt` pre-run guidance |