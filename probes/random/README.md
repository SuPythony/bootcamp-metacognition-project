# Manual Test Scenarios — Index

These files contain seeded dialogues for manually testing the Socratic tutor.
Each file has: the problem, why it stresses a specific part of the system,
simulated student inputs to play in order, and pass criteria to check manually.

Run a scenario by starting a new session in the app, typing the problem as the
first message, then playing the student inputs in sequence. Observe agent
behavior against the "what to watch for" and "pass criteria" sections.

---

| File | Domain | What it tests | Tools |
|---|---|---|---|
| `test_scenario_tickets.md` | math | Standard algebra word problem, happy path | algebra |
| `test_scenario_gaussian.md` | math | Hard integral, deep hint ladder, tool combo | graph + algebra |
| `test_scenario_fizzbuzz.md` | programming | Pyodide runner, pseudocode gate, bug interpretation | code_runner |
| `test_scenario_skill_gap.md` | math | Trivial problem, student knows almost nothing | algebra |
| `test_scenario_bad_explainer.md` | math | Student can't articulate reasoning, self-correction | algebra |

---

## What to look for across all scenarios

These are the cross-cutting behaviors to observe regardless of which scenario
you run:

- **One question per turn** — count question marks in every agent reply
- **No unprompted answers** — agent should never name the solution, formula,
  or next step without the student asking
- **Escape hatch flow** — if triggered, reflection must come after the answer
  (not before), and the reflection must be recorded in the thinking trace
- **Thinking trace delta** — open the thinking trace at wrap-up and check
  whether `initial_understanding` vs `final_understanding` shows real movement
- **Calibration** — at least one predict-then-check moment per session; miss
  handled warmly
- **Tool output framing** — tool results must be presented as data for the
  student to interpret, not as answers

## Logging

Every session writes to `backend/logs/llm.jsonl`. After a scenario, scan it:

```bash
# See all turns for a session
grep <session_id> backend/logs/llm.jsonl | python -m json.tool

# Check parse failures
grep '"parse_success": false' backend/logs/llm.jsonl
```

## Running the automated probe suite alongside manual tests

```bash
# Fast automated checks (no LLM)
cd backend && .venv/bin/pytest tests/test_socratic_constraints.py -v

# Full probe suite with manual check output
python -m tests.run_probes

# Single probe
python -m tests.run_probes --probe direct_answer_request

# Live LLM probes with manual review lines
.venv/bin/pytest tests/test_socratic_constraints.py -v --run-slow
# Bold yellow [MANUAL] lines in output require human review
```
