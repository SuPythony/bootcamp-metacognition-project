# Test Scenario: Horrible Explainer
**Domain:** math  
**Tools expected:** algebra  
**Difficulty:** moderate problem, communication stress test  
**Session length estimate:** 25–35 turns  

## Problem
Find the area of a triangle with base 10 cm and height 6 cm. Then find the
side length of a square with the same area.

## Why this is a good stress test
The problem is easy. The challenge is that the student cannot explain their
thinking clearly. They use vague language, skip steps, contradict themselves,
and get frustrated when asked to clarify. This tests:
- Whether the agent can extract signal from garbled explanations
- Whether the agent asks targeted clarifying questions rather than giving up
  and explaining itself
- Whether the reflection prompts produce anything useful from a student who
  resists reflecting

## Simulated student profile
Student knows the answer instinctively but cannot articulate reasoning. Gets
annoyed when asked to explain. Says "I just know" a lot. Uses "it" and "that
thing" instead of naming concepts.

## Simulated student inputs (play these vague and slightly annoyed)

1. "It's like half of the rectangle thing so you do the numbers."
2. "I multiplied them. It's 30."  ← skipped the ½, got wrong answer
3. "Wait no. It's like 60 but then you half it so 30. Yeah 30."
4. "Because that's how triangles work."  ← asked why ÷2
5. "I don't know how to say it. It's just the formula."
6. "The square thing is like... you reverse it? So the root."
7. "√30. I think."
8. "I can't really explain it, I just do it."
9. [asked for the wrap-up explanation] "The triangle is half a rectangle and
   the square is the same area so you root it."  ← slightly better but vague

## What to watch for

**Extracting signal from vague answers:**
- Input 1: "the numbers" and "rectangle thing" — agent should ask student to
  name the numbers and the shape, not correct them
- Input 2: student got 30 by multiplying 10×6÷2 correctly but said "multiplied
  them" without mentioning the half — agent must probe this gap, not accept it
- Input 3: student self-corrects mid-sentence. Agent should notice and ask
  "What made you change your answer?"  ← self-correction follow-up

**"I just know" responses:**
- Input 4, 5, 8: student refuses to explain. Agent must not accept this.
- Good response to "I just know": "Pretend you're explaining to someone who
  doesn't know the formula — what would you tell them first?"
- Must not repeat this exact phrasing more than once — vary the approach

**Reflection quality:**
- Input 9 is a shallow reflection — agent should evaluate it as shallow and
  ask one follow-up: "You said 'half a rectangle' — why is a triangle half
  a rectangle?"
- Maximum one follow-up per reflection — do not badger

**Calibration:**
- Student will predict high confidence (4–5) because they feel they know it
- After getting 30 wrong initially (input 2), calibration miss fires
- Agent must handle warmly: "You were confident and hit a snag — what was
  different from what you expected?"

**Self-correction moment (input 3):**
- Agent must explicitly note the self-correction in session state
- Follow-up question: "You caught that yourself — what tipped you off?"

## Pass criteria (manual)
- [ ] Agent never accepted "I just know" as a complete answer
- [ ] Agent varied its approach across inputs 4, 5, 8 — no repeated phrasing
- [ ] Self-correction in input 3 was explicitly noted and followed up
- [ ] Calibration miss after input 2 was handled warmly, not as a mistake
- [ ] Shallow reflection in input 9 got exactly one follow-up, not more
- [ ] Agent never explained the ½ formula — always asked questions to surface it
