# Plan: Next-Milestone Fixes — UI, Core Logic, Tooling, Harnesses

## Context

The schema migration (AgentSignal, three-key output) is complete and all 112 fast tests pass. However
several product features that were designed and wired in the backend are **not working end-to-end**:
the persona onboarding session is abandoned by the frontend; the thinking trace never computes
`final_understanding`; the LLM never sees tool `display_data`; session context omits metrics that
drive pacing decisions; science tools are stubs; and the domain prompts for programming, essay, and
science are too sparse for the agent to behave correctly. The probe suite covers constraint violations
but has zero domain-specific probes and no calibration/hint-escalation coverage.

---

## P0 — Broken flows (nothing works end-to-end for these)

### P0.1 — Persona onboarding flow is broken
**File:** `frontend/src/views/OnboardingView.tsx` lines 19-35  
**File:** `frontend/src/api/types.ts` lines 89-93  

`OnboardingView.handleSubmit()` calls `api.personaCreate()`, then **immediately** calls `api.sessionNew()` — it ignores the `session_id` returned in the "pending" response, abandoning the persona onboarding session the backend just created.

**Fix:**
1. Add `opening_message?: string` to `PersonaCreateResponse` in `api/types.ts`.
2. In `OnboardingView`: if `res.status === "pending"`, route to a mini-chat view using `res.session_id` and display `res.opening_message` as the first assistant message. When that chat session reaches `phase: "wrap_up"`, then call `api.sessionNew()` to begin the actual solving session.
3. In `backend/app/persona.py` `handle_persona_wrap_up()` (lines 152-174): accept a `session_id` param and call `session_mod.delete(session_id)` after `save_persona()` to avoid in-memory accumulation of completed onboarding sessions.

---

### P0.2 — Thinking trace `final_understanding` is always `None`
**File:** `backend/app/chat.py` lines 787-842 (`/session/{id}/thinking-trace` handler)  

All three summary fields are hardcoded `None`: `final_understanding`, `understanding_delta_label`, `understanding_delta_evidence`. The wrap-up view renders a scorecard, not a learning narrative.

**Fix:**
1. At the start of the wrap-up phase (when `_validate_phase` transitions to `wrap_up`), fire a lightweight LLM call (`call_classifier` or a new `call_summarizer`) with:
   - `initial_understanding` from the session
   - The last 4 student messages (synthesis turns)
   - Prompt: "One sentence: what has the student's understanding become? One word: significant | moderate | small. One sentence: what is the clearest evidence of change?"
2. Store the result on the session as `final_understanding: str`, `understanding_delta_label: str`, `understanding_delta_evidence: str`.
3. Return them from the thinking-trace endpoint.
4. Add `reflection_prompts` list (question + response + quality) to the trace response so the frontend can render individual reflections.

---

### P0.3 — LLM never sees tool `display_data`
**File:** `backend/app/chat.py` lines 576-586 (`_run_chat_turn` tool result injection)  

The tool result message sent to the LLM only includes `dispatch.get('result')` (the final answer string). The `display_data` (e.g., `{"steps": [...], "final": "..."}` from algebra) is never shown to the LLM. The agent cannot comment on the step-by-step derivation the student sees.

**Fix:** Change the tool result message to include both:
```python
f"[SYSTEM] Tool '{tool_name}' result:\n"
f"  answer: {dispatch.get('result')!r}\n"
f"  display (shown to student): {json.dumps(dispatch.get('display_data', {}))}\n"
f"Reply to the student now. Ask them to interpret this output. Do not call any tool."
```

---

## P1 — Core backend logic bugs

### P1.1 — Session context omits metrics and subproblem detail
**File:** `backend/app/session.py` lines 217-245 (`to_context_str()`)  

The LLM sees phase, active subproblem, and hint level — but NOT:
- `hints_per_subproblem` (agent can't decide when to escalate across subproblems)
- `direct_answer_requested` per subproblem (agent doesn't know escape hatch was triggered)
- subproblem `goal` field (set during decomposition, then forgotten)
- `self_corrections` count (agent can't decide when to fire self-correction reflection)
- `awaiting_reflection_response` already present ✓

**Fix:** Extend `to_context_str()` payload:
```python
"subproblems": [
    {"id": s.id, "description": s.description, "goal": s.goal,
     "status": s.status, "hints_given": s.hints_given,
     "direct_answer_requested": s.direct_answer_requested}
    for s in self.subproblems
],
"self_corrections": self.metrics.self_corrections,
"turns_in_phase": self.metrics.turns_total,  # proxy for pacing
```

---

### P1.2 — Tool dispatch does not validate tool result shape
**File:** `backend/app/plugin_registry.py` lines 171-212 (`dispatch_tool`)  

After `module.run(args, session)`, result is spread without validation. Missing `result` key → `KeyError` downstream in `_run_chat_turn`.

**Fix:** After `result = module.run(args, session)`, assert required keys:
```python
if "result" not in result:
    raise RuntimeError(f"Tool {domain}.{tool_name} run() did not return a 'result' key")
```

---

### P1.3 — Reflection quality dropped silently when `pending_reflection_index` is None
**File:** `backend/app/chat.py` lines 316-322  

If the agent sets `signal.last_reflection_quality` without a pending reflection, the quality is silently discarded. This happens when the agent evaluates quality two turns late.

**Fix:** Log a warning if quality arrives but `pending_reflection_index is None`. Optionally walk backwards through `session.reflection_prompts` to find the most recent one with `quality=None` and attach it there.

---

## P2 — Tooling: science stubs and math edge cases

### P2.1 — Science tools are stubs (crash on any call)
**Files:** `backend/specializations/science/tools/graph.py` line 3, `data_table.py` line 3  

Both raise `NotImplementedError`. Any science session that triggers a tool call gets a 502.

**Fix for `graph.py`:** Import and call `specializations.math.tools.graph.run(args, session)` — the math graph tool works for any expression. Science graphs differ only in labeling; reuse is correct.

**Fix for `data_table.py`:** Implement a minimal version:
- Accept `{"columns": [...], "rows": [[...], ...]}` 
- Return `{"result": "table rendered", "display_data": {"columns": [...], "rows": [...]}, "ui_component": "DataTable"}`
- No computation — just pass data through for the frontend to render.

---

### P2.2 — Math algebra edge cases
**File:** `backend/specializations/math/tools/algebra.py`  

- **Line 166-177 (solve):** If expression contains multiple `=` signs, only the first is used to split. Should validate: if more than one `=` in the input, return a clear error "cannot solve multi-equality expression; please simplify to one equation."
- **Line 187:** `sympy.solve` returns `[]` for unsolvable equations — distinguish from single-solution `[0]`. Return `{"result": "no real solution", ...}` explicitly.
- **Line 184-185:** Factorization check only tests `Mul` type — misses single-factor results. Use `sympy.factor()` directly on the expression instead.

### P2.3 — Math graph edge cases
**File:** `backend/specializations/math/tools/graph.py`  

- **Lines 62-63:** Validate `x_range` against NaN/Inf before computing: `if not (math.isfinite(x_range[0]) and math.isfinite(x_range[1])): raise ValueError(...)`.
- **Lines 100-106:** Complex outputs silently become NaN. Log a warning and return an explicit error field `"warning": "expression produces complex values; plotted real part only"` in `display_data`.
- **Line 115:** Scale sample density: `n_points = max(500, min(2000, int(abs(x_range[1]-x_range[0]) * 50)))`.

---

## P3 — Domain prompts: sparse and incomplete

All three under-specified domain prompts must be substantially expanded before the agent can behave correctly in those domains. These are prompt files — no Pydantic/Python changes.

### P3.1 — Programming prompt (9 lines → robust)
**File:** `backend/specializations/programming/prompt.txt`  

Add:
- Pseudocode-first gate: "Never write code for the student. When they ask for code, ask for pseudocode first. Only after pseudocode is confirmed should they translate to Python."
- Code runner usage: "Use `code_runner` to run the student's code after they write it. Always ask them to predict the output before running. Ask them to explain the actual output afterward."
- Error handling: "When code produces an error, ask 'What do you think that error message means?' before pointing at the line."
- Scope: "code_runner supports standard Python (no file I/O, no network). Advise students if they try unavailable features."

### P3.2 — Essay prompt (8 lines → robust)
**File:** `backend/specializations/essay/prompt.txt`  

Add:
- Claim specificity gate: "Never accept a broad opinion as the claim. Ask 'Can you make that more specific?' until the claim is falsifiable and specific."
- Evidence quality: "Ask 'Is that evidence (observation, data, logic) or just opinion?' when the student cites anecdote as proof."
- Counter-argument: "After the student states their claim, ask 'What would someone who disagrees say?' Do not move to drafting until they've genuinely engaged with it."
- No drafting: "Never write a sentence of the essay. You may ask the student to revise a specific sentence they wrote, but you write nothing."
- OutlineTree directive: "When the student's claim + 2 evidence points + counter-argument are confirmed, emit a `ui_directive` with `component: 'OutlineTree'`, `domain: 'essay'`, `props: {nodes: [...]}` with the confirmed structure."

### P3.3 — Science prompt (5 lines → robust)
**File:** `backend/specializations/science/prompt.txt`  

Add:
- Observable grounding: "For every scientific claim, ask 'How would you test that?' before offering any framing."
- Tool usage: "Use the `graph` tool when the student plots data or describes a relationship. Use `data_table` when the student lists observations or measurements. Ask them to interpret the output."
- No formulae given: "Do not state laws or formulae. Ask 'What do you remember about [concept]?' and wait."
- Experimental design: "When a student proposes an experiment, ask 'What would you keep constant? What would you change? What would you measure?'"

---

## P4 — Probe and harness additions

### P4.1 — Domain-specific negative probes (canned, no LLM)
**File:** `backend/tests/test_socratic_constraints.py`  

Add canned bad-reply entries to `test_probe_canned_bad_reply_fails_assertions` for:
- `programming_no_code_written`: reply contains Python `def` keyword → fails
- `programming_must_ask_pseudocode_first`: reply gives working code without asking for pseudocode → fails
- `essay_claim_too_broad`: reply accepts "social media is bad" without pushing for specificity → no assertion helper yet (add `assert_claim_refined`)
- `math_tool_not_called_for_algebra`: reply contains a numeric solve done inline rather than via tool → `assert_no_inline_computation` (new helper: regex for `= [0-9]` without preceding tool call)

### P4.2 — Calibration workflow probe (slow)
**File:** `backend/tests/probes.py`  

Add probe `calibration_predict_check`:
- Messages: student in solving phase with active subproblem
- Assert: reply contains `emit_calibration_check: true` in signal (or CalibrationCheck directive in control)
- Assert: reply does NOT contain `phase: "wrap_up"` on the same turn (phase guard)

Add probe `hint_escalation_one_step`:
- Messages: two consecutive stuck turns on same subproblem at hint_level=1
- Assert: `signal.hint_level == 2` (not 3 or higher — no jumping)

### P4.3 — Tool sequencing probe (slow)
**File:** `backend/tests/probes.py`  

Add probe `math_tool_before_answer`:
- Messages: student attempts algebra step, agent should invoke tool
- Assert: reply's `control.tool_call` is non-null (agent calls tool, doesn't answer inline)
- Assert: `assert_no_inline_computation(reply)` (new helper)

---

## Critical files

| File | Change |
|------|--------|
| `frontend/src/views/OnboardingView.tsx` | Route pending persona session through chat, not new session |
| `frontend/src/api/types.ts` | Add `opening_message?` to `PersonaCreateResponse` |
| `backend/app/chat.py` | P0.2 (thinking trace wrap-up LLM call), P0.3 (display_data in tool msg) |
| `backend/app/session.py` | P1.1 (extend to_context_str) |
| `backend/app/persona.py` | P0.1 (delete onboarding session after save_persona) |
| `backend/app/plugin_registry.py` | P1.2 (validate tool result keys) |
| `backend/specializations/science/tools/graph.py` | P2.1 (delegate to math graph) |
| `backend/specializations/science/tools/data_table.py` | P2.1 (pass-through implementation) |
| `backend/specializations/math/tools/algebra.py` | P2.2 (edge cases) |
| `backend/specializations/math/tools/graph.py` | P2.3 (NaN/inf, complex, density) |
| `backend/specializations/programming/prompt.txt` | P3.1 (expand to 60+ lines) |
| `backend/specializations/essay/prompt.txt` | P3.2 (expand to 60+ lines) |
| `backend/specializations/science/prompt.txt` | P3.3 (expand to 60+ lines) |
| `backend/tests/test_socratic_constraints.py` | P4.1 (new canned probes) |
| `backend/tests/probes.py` | P4.2, P4.3 (calibration + tool sequencing probes) |

---

## Order of execution

1. **P0 fixes first** — the persona flow, thinking trace, and display_data are visible feature breaks.
   - P0.3 (display_data) is a 3-line change; do it first.
   - P0.2 (thinking trace) requires a new LLM call at wrap-up; do second.
   - P0.1 (persona flow) touches frontend and backend; do third.
2. **P1 backend bugs** — extend `to_context_str`, validate tool result, fix reflection quality drop.
3. **P2 tooling** — science tools first (unblock the domain), then math edge cases.
4. **P3 prompts** — programming, essay, science (no code changes; can run probes immediately after).
5. **P4 harnesses** — add probes after prompts are updated so they run against the real content.

---

## Verification

```bash
# After P0-P2:
cd backend && .venv/bin/pytest -q                  # all fast tests must pass

# After P3 (prompts):
python -m tests.run_probes                          # all 9 existing probes must pass
python -m tests.run_probes --probe programming_no_code_written  # new domain probe

# Manual (use testuser, start backend + frontend):
# 1. New user "probe_user1" → should see 2-turn persona intake, then be routed to solving session
# 2. Solve a math problem end-to-end → check wrap-up shows final_understanding (not blank)
# 3. Science session → trigger graph tool → should not crash with 502
# 4. Programming session → type Python code directly → agent should ask for pseudocode first
# 5. Essay session → type "social media is bad" → agent should push for specificity, not accept it
```
