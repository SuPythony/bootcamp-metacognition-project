# Probe 2 — Bouncing Ball (Aha Moment, Graph + Sympy)

## Problem to submit
```
A ball is dropped from 1 metre. Each bounce reaches 2/3 of the previous height.
What is the total distance the ball travels?
```

## Why this problem
The aha moment: infinitely many bounces, finite total distance. Almost every
student's first instinct is "infinite" — the graph and sympy result together
produce a genuine surprise. Three clean subproblems. The graph of partial sums
converging is visually compelling and does the pedagogical work better than any
explanation could. Sympy verifies the geometric series sum cleanly.

---

## Exact prompts — type verbatim in order

```
T1: "The ball keeps bouncing forever so the distance must be infinite?"
T2: "Each bounce is 2/3 of the last. So heights are 1, 2/3, 4/9, 8/27..."
T3: "The total distance going down is 1 + 2/3 + 4/9 + ... and then the same
     going back up?"
T4: "So it's 2 times the sum minus the first drop? Like 2*(sum) - 1?"
T5: "The sum looks like 1 divided by (1 minus 2/3)?"
T6: "That gives 3. So total distance is 2*3 - 1 = 5 metres?"
T7: "That can't be right. Infinite bounces but only 5 metres?"
T8: "I guess the bounces get so small they barely add anything."
T9: "So a series can converge even if it has infinite terms."
```

## The aha moment
T7 is the aha. The student has the right answer and doesn't believe it.
Agent must NOT reassure ("yes that's correct!"). Instead: "What would you
need to check to convince yourself?" — force them to verify.

## Tool calls expected
- Graph tool: called after T2 or T3. Plot partial sums of the series
  (sum of first N terms vs N) to show convergence visually.
  Expression: something like cumulative sums — agent should think about
  how to frame this for the tool. Ask student: "What do you notice about
  where this curve is heading?"
- Algebra tool: called after T5 to verify `sum(2/3**n, n, 0, oo)` = 3.
  After result arrives: "Does this match what you calculated? What does
  the formula tell you?"

## Subproblems student should find
1. Write out the pattern of heights
2. Set up the total distance as an infinite series
3. Evaluate the geometric series sum and interpret the result

## Pass criteria
- [ ] T1: agent did not immediately correct "infinite" — asked what the
      student thought would happen to the later bounces
- [ ] Graph tool called and student asked to interpret convergence before
      agent says anything about it
- [ ] T7: agent did not confirm the answer — asked the student to verify
- [ ] T9: agent asked "can you say that more precisely?" — shallow
      reflection should get one follow-up
- [ ] Sympy result presented as verification data, not as explanation

## Backend checks
```bash
grep '"parse_success": false' backend/logs/llm.jsonl
grep '"event": "llm_error"' backend/logs/llm.jsonl
# Graph tool must appear
grep 'graph' backend/logs/llm.jsonl | grep -v '"tool_call": null'
```
