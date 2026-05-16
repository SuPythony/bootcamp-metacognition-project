# Test Scenario: Tickets Word Problem
**Domain:** math  
**Tools expected:** algebra (sympy)  
**Difficulty:** moderate  
**Session length estimate:** 20–30 turns  

## Problem
A school is selling tickets for a play. Student tickets cost $4 and adult tickets
cost $7. On opening night, 200 tickets were sold and the total revenue was $980.
How many of each type of ticket were sold?

## What to watch for

**Clarification phase:**
- Agent should ask what the student already understands before touching the problem
- Student should be pushed to name the two unknowns themselves
- Good clarification question: "What are the two things you don't know yet?"

**Decomposition phase:**
- Student should find: (1) write the ticket count equation, (2) write the revenue
  equation, (3) solve the system, (4) verify
- Agent must NOT list these — nudge only

**Solving loop:**
- Common student mistake: tries guess-and-check rather than setting up equations.
  Agent should redirect with a question, not a correction.
- Algebra tool should be invoked for the substitution/elimination step
- Agent must present tool output as data: "Here's what the algebra gives us —
  what does this tell you?"

**Calibration moment:**
- Student often feels confident after writing equations but gets arithmetic wrong
- Good predict-then-check moment before the solve step

**Escape hatch likelihood:** medium — substitution step is where frustration peaks

## Simulated student inputs (play these in order)

1. "I need to find how many student and adult tickets were sold."
2. "I think I need two equations but I'm not sure how to set them up."
3. "One equation is s + a = 200?"
4. "The other one has to do with money... 4s + 7a = 980?"
5. "Can you just solve it for me now?"  ← escape hatch attempt
6. "I got stuck trying to figure out which variable to substitute."
7. [after answer shown] "I replaced s with 200 - a in the second equation."
8. "So a = 60 and s = 140. Let me check: 140×4 + 60×7 = 560 + 420 = 980. Yes!"
9. "I understand it now — you use two equations because there are two unknowns
   and one equation isn't enough to pin them both down."

## Pass criteria (manual)
- [ ] Agent never gave the equations unprompted
- [ ] Algebra tool was called for the solve step, not done in chat
- [ ] Escape hatch triggered the reflection gate before showing answer
- [ ] Thinking trace shows understanding delta between inputs 1 and 9
