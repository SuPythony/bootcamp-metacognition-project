# Test Scenario: Big Skill Gap
**Domain:** math  
**Tools expected:** algebra  
**Difficulty:** easy problem, stressed student  
**Session length estimate:** 30–40 turns (long — hint ladder goes deep)  

## Problem
Solve for x: 2x + 6 = 14

## Why this is a good stress test
This is a trivially easy problem. The point is not the problem — it is testing
how the agent handles a student who is genuinely lost on foundational concepts.
The hint ladder should go all the way to level 5. Escape hatch is likely.
Tests patience, tone, and whether the agent keeps asking questions even when
the student clearly has no idea.

## Simulated student profile
Student understands almost nothing. Does not know what "solve for x" means.
Does not know what an equation is. Has seen numbers and letters together before
but cannot explain why.

## Simulated student inputs (play these straight — do not hint that you know more)

1. "I don't know what x means."
2. "Is x like a letter standing in for a number?"
3. "I don't know which number though."
4. "Can't I just try numbers until one works?"  ← guess-and-check attempt
5. "I tried x=3 and got 12 not 14. I tried x=4 and got 14. So x=4?"
6. "But how was I supposed to know to try 4 without guessing?"
7. "What does the equals sign mean exactly?"
8. "So both sides have to be the same number?"
9. "If I take 6 away from both sides... 2x = 8?"
10. "Then x is half of 8 so x = 4."
11. "Oh it's the same as what I guessed but now I know WHY."

## What to watch for

**Hint ladder stress test:**
- Input 1–3: agent should NOT explain what x is — ask questions that lead student
  to figure it out. "Have you seen a symbol standing in for something unknown before?"
- Input 4–5: guess-and-check is valid intuition. Agent should validate the
  approach then ask "Is there a way to do this without guessing?"
- Input 7: "what does equals mean" is a real clarification moment. Agent should
  treat it seriously, not rush past it
- By input 9 the student is essentially doing algebra correctly — agent should
  recognise this and confirm without over-explaining

**Tone under repeated confusion:**
- Agent must stay warm across 10+ turns of a student who barely understands
- Must not become repetitive ("Good question! Let's think about this...")
- Must not give increasingly long explanations — shorter and more targeted as
  confusion deepens

**One-question discipline:**
- With a confused student, the temptation to ask multiple questions is highest
- Watch for any turn where agent asks "Do you know what X is? And what about Y?"

**Escape hatch:**
- If student hits input 6 and says "just tell me how" — this is a realistic
  escape hatch moment
- Reflection gate should fire: "Before I show you — where exactly did your
  thinking get stuck?"

## Pass criteria (manual)
- [ ] Agent never explained what x is — always asked questions to surface it
- [ ] Guess-and-check was validated before being redirected
- [ ] Tone stayed warm for the full session — no mechanical repetition
- [ ] One question per turn held even when student was most confused
- [ ] Understanding delta is visible: "I don't know what x means" → "I know
     why the answer is 4, not just that it is"
