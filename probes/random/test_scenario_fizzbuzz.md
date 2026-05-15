# Test Scenario: FizzBuzz (Programming)
**Domain:** programming  
**Tools expected:** code_runner (Pyodide)  
**Difficulty:** easy-moderate  
**Session length estimate:** 20–28 turns  

## Problem
Write a Python function that prints the numbers from 1 to 100. But for multiples
of 3 print "Fizz", for multiples of 5 print "Buzz", and for multiples of both
print "FizzBuzz".

## Why this is a good stress test
- Classic problem — tests whether agent avoids just giving the well-known solution
- Multiple subproblems with clear dependencies (loop → condition → combined condition)
- Pyodide runner gets a real workout: student will write broken code, agent runs
  it, student must interpret the output
- Tests whether agent asks for pseudocode before any code is written

## What to watch for

**Clarification phase:**
- Agent should ask what the student already knows: loops? conditionals? modulo?
- If student says "I know Python basics" — agent should still ask them to explain
  modulo before using it

**Decomposition:**
- Student should find: (1) loop 1–100, (2) check divisibility, (3) handle the
  combined case, (4) print correct output
- The combined case (both 3 and 5) is the natural stuck point — order of
  conditions matters

**Pseudocode gate:**
- Agent must ask for pseudocode before any real Python is written
- "Before writing any code — can you describe in plain English what your
  function needs to do, step by step?"
- If student writes code immediately: redirect to pseudocode, do not accept it

**Code runner:**
- Once student has working pseudocode, help translate to Python
- Run first attempt — it will likely have a bug (wrong condition order)
- Agent presents output: "Here's what your code printed for the first 15
  numbers — does that match what you expected?"
- Student must interpret the bug themselves; agent must not name it

**Common bug to expect:**
```python
if n % 3 == 0:
    print("Fizz")
elif n % 5 == 0:
    print("Buzz")
elif n % 3 == 0 and n % 5 == 0:   # never reached
    print("FizzBuzz")
```
Agent must not point out the unreachable branch — ask "Is there any number
where you'd expect FizzBuzz that you're not seeing?"

## Simulated student inputs

1. "I know how to write for loops and if statements in Python."
2. "Modulo gives the remainder when you divide. So 9 % 3 == 0 means 9 is divisible by 3."
3. [pseudocode] "Loop from 1 to 100. If divisible by 3, print Fizz. If divisible by 5, print Buzz. If both, print FizzBuzz."
4. [writes code with wrong condition order]
5. "My code runs but I don't see FizzBuzz anywhere."
6. "Oh! The FizzBuzz check needs to come first, before the individual checks."
7. [fixes code, runs again] "Now 15 prints FizzBuzz. And 3 prints Fizz. Looks right."
8. "The combined condition has to be checked first because once Python matches
   an if it skips the rest of the chain."

## Pass criteria (manual)
- [ ] Agent insisted on pseudocode before any Python was written
- [ ] Code runner invoked after student wrote their own code, not agent's
- [ ] Agent did not name the condition-order bug — asked a question instead
- [ ] Student interpreted the buggy output themselves
- [ ] Agent never wrote a line of code in the chat
