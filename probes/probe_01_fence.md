# Probe 1 — Fence Optimization (Hard Math, Many Subproblems)

## Problem to submit
```
A farmer has 100 metres of fencing. He wants to enclose a rectangular field
against a straight barn wall, so only three sides need fencing. What dimensions
give the maximum enclosed area?
```

## Why this problem
Five natural subproblems, all student-discoverable. Two tool calls (algebra for
differentiation, graph for the parabola). The "barn wall" setup requires genuine
clarification — students almost always try to fence all four sides. Frustration
peaks at the derivative step, making escape hatch likely. The verify step
(confirm it's a maximum, not minimum) is where most students stop too early.

---

## Exact prompts — type verbatim in order

```
T1: "I need to find the length and width of the field."
T2: "Wait — one side is the barn wall so I only have three sides to fence?"
T3: "So if the side parallel to the barn is x, the other two sides are each
     (100 - x) / 2?"
T4: "The area is x times (100 - x) / 2."
T5: "I expand it to get 50x - x^2 / 2."
T6: "I need to find the maximum. Do I differentiate?"
T7: "The derivative is 50 - x. Set it to zero... x = 50?"
T8: "So the two shorter sides are each 25 metres."
T9: "But how do I know it's a maximum and not a minimum?"
T10: "The second derivative is -1 which is negative so it's a maximum."
T11: "The field is 50 metres along the barn and 25 metres deep. Area is 1250
      square metres."
```

## Clarification to watch (T2)
Agent must NOT confirm the barn setup. It should ask: "What do you think
that means for which sides need fencing?" T2 is the student realising it
themselves — agent should only ask, never confirm until T3 is correct.

## Tool calls expected
- Algebra tool: called after T6 or T7 to differentiate `50*x - x**2/2`
  and solve for x. Agent must NOT do this in chat.
- Graph tool: called around T5 or T6 to show the parabola. After rendering,
  agent asks: "Where does the maximum appear on this curve?"

## Subproblems student should find
1. Interpret the constraint (three sides, total 100m)
2. Express area as a function of one variable
3. Differentiate and solve for the critical point
4. Verify it is a maximum (second derivative test)
5. State both dimensions and the area

## Pass criteria
- [ ] T2: agent asked a question, did not confirm the barn setup
- [ ] T5: algebra tool called for differentiation, not done in chat
- [ ] Graph tool called; student asked to interpret it before agent says anything
- [ ] T9: agent did not skip to "yes it's a maximum" — asked why
- [ ] All five subproblems proposed by the student, not listed by agent
- [ ] Thinking trace: initial understanding ("find length and width") vs final
      ("maximise area under a constraint using calculus") shows clear delta

## Backend checks
```bash
grep '"parse_success": false' backend/logs/llm.jsonl
grep '"event": "llm_error"' backend/logs/llm.jsonl
# Expect two tool call entries
grep '"tool_call"' backend/logs/llm.jsonl | grep -v '"tool_call": null' | wc -l
```
