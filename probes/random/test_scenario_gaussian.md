# Test Scenario: Gaussian Integral
**Domain:** math  
**Tools expected:** graph (matplotlib), algebra (sympy — will fail gracefully)  
**Difficulty:** hard  
**Session length estimate:** 25–35 turns  

## Problem
Evaluate the integral from -∞ to +∞ of e^(-x²) dx.

## Why this is a good stress test
- sympy CAN evaluate this (`sqrt(pi)`) — tests algebra tool happy path
- The graph of e^(-x²) is visually compelling and helps intuition — tests graph tool
- The standard proof uses a polar-coordinates trick the student is unlikely to know,
  creating a realistic multi-hint escalation
- Tests whether agent handles "student has genuinely no idea" gracefully without
  just giving the answer

## What to watch for

**Clarification phase:**
- Agent should ask what the student knows about this integral before anything else
- Student may say "I've never seen this" — agent should note it and move on,
  not stall

**Decomposition — this is the hard part:**
- Subproblems are non-obvious: (1) understand why standard antiderivative fails,
  (2) set up I², (3) convert to polar, (4) evaluate, (5) take square root
- Student is unlikely to find these unprompted — agent must use questions to
  surface them one at a time without naming them
- Good question at step 1: "What happens when you try to find an antiderivative
  of e^(-x²) the normal way?"

**Graph tool:**
- Agent should invoke graph tool early to show the bell curve shape
- After rendering: "What do you notice about the tails of this curve? What does
  that suggest about whether the integral converges?"

**Algebra tool:**
- Call sympy to verify `integrate(exp(-x**2), (x, -oo, oo))` → `sqrt(pi)`
- Present as: "Let's check what the algebra gives us — does this match what
  you'd expect from the geometric argument?"
- Note: sympy will return the answer directly here. Agent must not present this
  as the explanation — it's a numerical check, not a proof.

**Hint ladder expectation:**
- This problem likely needs hint level 4–5 for most students
- Level 5 hint: "The trick is to compute I² instead of I directly. What would
  I² look like as a double integral?"
- Agent must not skip to this — escalate through levels 1–4 first

**Escape hatch likelihood:** high — this is a genuinely hard problem

## Simulated student inputs

1. "I have no idea where to start with this."
2. "I tried to find the antiderivative but I don't think e^(-x²) has one."
3. "So how do we integrate something with no antiderivative?"
4. "What's I²? Like the integral squared?"
5. "Oh so it becomes a double integral over the whole plane?"
6. "I'm lost on the polar coordinates step."  ← likely escape hatch point
7. [after hint/escape] "So r dr dθ replaces x and y somehow?"
8. "The inner integral gives (1/2) and the outer gives 2π so I² = π?"
9. "So I = √π. That's a weird answer for an integral."

## Pass criteria (manual)
- [ ] Graph tool invoked and student asked to interpret the shape
- [ ] Algebra tool used to verify, not to explain
- [ ] Agent did not jump to the I² trick without escalating through earlier hints
- [ ] Student who said "I have no idea" was not stalled in clarification phase
- [ ] sympy result presented as data, not as proof
