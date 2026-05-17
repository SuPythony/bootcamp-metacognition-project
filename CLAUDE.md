# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Current State

**Frontend and backend core loop are fully implemented and running end-to-end.** The Socratic chat loop works in production (OpenRouter → Gemini 2.5 Flash), phase transitions are validated, the subproblem panel updates live, the thinking trace renders at wrap-up, LaTeX renders throughout, the algebra tool works, and CalibrationCheck/ReflectionPrompt widgets render inline in real-LLM mode. Mock mode (`VITE_USE_MOCK=true`) runs a scripted 7-turn conversation without any API calls. Persona onboarding now routes through a real chat session end-to-end. Science tools (graph, data_table) are fully implemented. Domain prompts for programming, essay, and science are substantially expanded. The thinking-trace endpoint now computes both `initial_understanding` (captured at clarification exit) and `final_understanding` (synthesised at wrap-up) via lightweight LLM summariser calls, so the wrap-up diptych and delta chip render with real data.

### What is real and working

- **Backend** — all FastAPI routes are real implementations (not placeholders): `/session/new` with classifier-based domain detection, `/chat` with full session state machine, `/persona/create`, `/persona/reset`, `/session/{id}/thinking-trace`, `/specializations`, `/tools/{tool_name}` dispatch. Plugin registry loads all specializations at startup.
- **Frontend** — all views and components are implemented: `OnboardingView`, `SessionView`, `WrapUpView`, `ChatPane`, `SubproblemPanel`, `ToolPane`, `ThinkingTraceDrawer`, `HintBadge`, `ConfidenceWidget`, `CalibrationCheck`, `ReflectionPrompt`. Error boundary in `App.tsx` catches render crashes. API client surfaces real backend error messages (not just "Something went wrong").
- **Mock mode** — `mock.ts` runs a scripted 7-turn conversation (clarification → decomposition → solving → wrap_up) with inline directives, subproblem updates, CalibrationCheck, ReflectionPrompt, and a rich thinking trace. Toggle via `VITE_USE_MOCK=true`.
- **Phase machine** — illegal phase transitions (e.g. model jumping `clarification → wrap_up`) are clamped to current phase with a warning log rather than crashing the conversation. Bug fixed: `_apply_agent_response` no longer overwrites the already-validated phase (was re-applying the raw unclamped value).
- **Math tools** — `algebra.py` and `graph.py` are both fully implemented. `algebra.py` uses sympy with implicit multiplication (`2x`, `3(x+1)`). `graph.py` uses matplotlib Agg backend, returns `data:image/png;base64`, clips asymptotes, also handles implicit multiplication.
- **LaTeX rendering** — KaTeX renders throughout: chat messages, subproblem panel, thinking trace, RuleRecallPrompt, AlgebraSteps. All math is routed through `MathText.tsx` (react-markdown + remark-math + rehype-katex). Algebra tool uses `sympy.latex()` for step output.
- **CalibrationCheck + ReflectionPrompt** — components render inline in the chat. Backend auto-injects the widgets from signal fields: agent emits `signal.emit_calibration_check: true` or `signal.emit_reflection: "trigger_type"` and the backend converts these to `ui_directives` with backend-curated question text. The model never generates the question text — it only names the trigger type. Phase guard prevents `wrap_up` transition on the same turn as `emit_calibration_check`. The reflection question stored in the session and shown in the directive are always the same (chosen once in `_apply_agent_response`, reused in `_build_chat_response`).
- **Tool-call loop** — fixed: unconditional assistant message before tool result, same-tool deduplication guard, tool result sent as `"role": "user"` (Gemini follows user-role instructions more reliably than system).
- **JSONL call logging** — `backend/logs/llm.jsonl` receives every event: `llm_call` (tutor, with `user_message_preview`), `llm_classifier` / `llm_classifier_error`, `llm_summarizer` / `llm_summarizer_error`, and `chat_turn` (phase, hint_level, user_message, agent_reply_preview, tool_called per `/chat` call). `chat_turn` events are also written to `backend/logs/chat.jsonl` as a separate per-turn stream. Set `LOG_LLM_CALLS=false` to suppress both files. `backend/logs/` is gitignored except `.gitkeep`. Use `backend/scripts/view_logs.py` to browse `llm.jsonl` in a local web UI (requires `flask`; see script docstring).
- **Probe suite** — `backend/tests/probes.py` defines 17 probes covering Socratic discipline constraints (direct answer refusal, escape hatch, subproblem enumeration, JSON schema, one-question-per-turn, no code written, no essay drafted), schema compliance, Pólya heuristic application, and domain-specific rules (`programming_pseudocode_first`, `math_tool_before_answer`, `essay_claim_specificity`, `hint_precondition_enforced`, `student_answer_no_reasoning`, `polya_working_backward`, `clarification_uses_thinking`, `essay_counter_argument_engaged`). Assertion helpers include `assert_no_code_written`, `assert_no_inline_algebra`, `assert_claim_pushed`, `assert_hint_level_null_or_zero`, `assert_reply_contains_any`, `assert_no_direct_confirmation`, `assert_thinking_non_empty`, `assert_tool_call_set`. Each probe carries `manual_checks` for human review. Run via `backend/tests/run_probes.py` (no server needed) or as slow pytest tests with `--run-slow`.
- **Split prompt architecture** — `backend/app/prompts/v1/` holds 8 files assembled per-turn: `core.txt` (always), `phase_{phase}.txt` (one per phase), `block_tool_result.txt` / `block_calibration.txt` / `block_reflection_eval.txt` (conditional on session state). `load_base_prompt(variant_key, session, had_tool_result)` in `variants.py` does the assembly. `chat.py` calls it every turn with the live session object; probes pass a minimal `_PhaseStub`. Domain prompts (`specializations/{domain}/prompt.txt`) are concatenated after the base.
- **Prompt variant system** — `backend/app/prompts/variants.py` maps string keys to prompt sources. Base variants (`base:v1`, etc.) map to **folders**; domain variants (`math:v1`, etc.) map to flat files. `load_base_prompt(variant_key, session)` is used in `chat.py`; `load_combined(domain)` (probes/tests only, no live session) calls `load_base_prompt(session=None)` returning `core.txt` only. Server-run variant is set via `PROMPT_VARIANT_BASE` / `PROMPT_VARIANT_DOMAIN` env vars.
- **Initial-understanding capture** — `session.initial_understanding` is populated automatically at the clarification → next-phase transition by `_maybe_capture_initial_understanding` in `chat.py`. The helper calls `llm.call_initial_understanding_summarizer` (cheap classifier model) over the session's clarification-phase student messages and stores the returned one-sentence summary. Idempotent — once set, the field is never overwritten on re-entries. Logged as `llm_initial_summarizer` / `llm_initial_summarizer_error` events. There is no `signal.initial_understanding` field; capture is deterministic backend-side and does not rely on the agent emitting anything (mirrors how `final_understanding` is built at wrap-up, avoiding the dormant-signal failure mode that affected `emit_reflection`).
- **Summariser tone** — `call_summarizer`'s system prompt addresses the student in second person ("You came to see…", "You moved from … to …") and explicitly forbids graded language ("fragmented", "incomplete", "partial", "shallow"). Same constraints apply to `call_initial_understanding_summarizer`. Tested via `test_call_summarizer_system_prompt_enforces_tone` — if a future edit drops the constraints, the test fails immediately.

### What is still a stub

- **SSE streaming** — `stream_tutor()` in `backend/app/llm.py` raises `NotImplementedError`. All chat responses are currently non-streaming (full JSON on completion). Implement SSE for word-by-word streaming (see Priority 3).
- **Seeded dialogue tests** — `backend/tests/test_socratic_constraints.py` has assertion helpers and probe-backed slow tests, but no deterministic seeded dialogue test cases (canned turn sequences with hardcoded LLM replies). The probe suite covers live-LLM regression; seeded dialogues would give a fast, deterministic gate (see Priority 4).
- **EC2 deploy** — deploy artifacts shipped under `deploy/` (bootstrap.sh, deploy.sh, nginx + systemd templates, hostname parameterized via `deploy/deploy.env`). First deploy still pending — nothing has been run on a real box yet.
- **Critique Mode** — designed and prompt-drafted (`critic_base.txt`) but deferred to v1.1.
- **Calibration & reflection signals still dormant** — `ThinkingTraceDrawer` renders Calibration and Reflection sections, but in real sessions the agent rarely emits `emit_reflection` or `emit_calibration_check`, so the sections are mostly empty. The UI is wired; the prompt needs tuning to actually trigger these flows. (Note: the `initial_understanding` / understanding-delta rendering, which was previously affected by the same kind of dormancy at the *backend* level, is now solved by deterministic backend capture — see the "Initial-understanding capture" entry above. Reflection/calibration require a similar fix on the *prompt* side.)

### Next milestones (in order)

1. Fix calibration/reflection emission: tune prompts so the agent reliably emits the signals (or move to deterministic backend capture, as was done for `initial_understanding`)
2. Implement SSE streaming in `stream_tutor()` and wire it into the frontend ChatPane
3. Add seeded dialogue test cases to `test_socratic_constraints.py`
4. Deploy to EC2

### Recent changes (prompt-upgrade branch)

The following were fixed/implemented in the `prompt-upgrade` milestone (P0–P4 + L1/U1/E1):

**P0–P4 (core loop fixes)**
- **Persona onboarding end-to-end** — `OnboardingView` now routes a "pending" persona response to a `persona_session` route in `App.tsx`, which runs the 2-turn intake as a real `SessionView` with `domain="persona"`. After the agent emits `wrap_up`, the `onOnboardingComplete` callback fires and routes back to onboarding Step 2. `handle_persona_wrap_up()` deletes the onboarding session from memory after saving the persona.
- **Two-step onboarding UI** — `OnboardingView` is now a two-step form: Step 1 asks for username only (calls `personaCreate`), Step 2 asks for the problem. A `confirm_new` status from `/persona/create` shows an inline "Start fresh?" confirmation before creating an account, preventing typo-driven account creation. "← Not {name}?" resets to Step 1.
- **Thinking trace `final_understanding`** — the `/session/{id}/thinking-trace` endpoint now calls `llm.call_summarizer()` (uses the cheap classifier model) with the student's initial understanding and the last 4 student messages. Returns `final_understanding`, `understanding_delta_label`, `understanding_delta_evidence`. Gracefully returns `None` on failure.
- **Tool `display_data` sent to LLM** — the tool result message now includes `display_data` (the full step-by-step algebra output, table data, etc.) so the agent can comment on what the student sees, not just the raw result string.
- **Session context extended** — `to_context_str()` now includes subproblem `goal`, `hints_given`, `direct_answer_requested` per subproblem, plus session-level `self_corrections` and `turns_total`. Gives the agent the pacing data to make escalation decisions.
- **Tool result validation** — `dispatch_tool()` validates that `module.run()` returns a dict with a `'result'` key, raising `RuntimeError` immediately instead of `KeyError` deep in `_run_chat_turn`.
- **Reflection quality orphan fix** — if `last_reflection_quality` arrives without a pending reflection index (agent evaluated two turns late), the backend now walks backwards to find and attach quality to the most recent un-evaluated reflection, with a warning log if none is found.
- **Science tools implemented** — `science/tools/graph.py` delegates to the math graph implementation. `science/tools/data_table.py` is a full pass-through formatter returning `{"result": "...", "display_data": {"columns": ..., "rows": ...}, "ui_component": "DataTable"}`.
- **Math tool edge cases** — algebra: multi-`=` validation, factorization fixed (`!=` instead of `isinstance(Mul)`), "No real solution" wording. Graph: `x_range` isfinite validation, complex-output warning, adaptive sample density (`max(500, min(2000, int(span*50)))`).
- **Domain prompts substantially expanded** — programming: 9 → ~70 lines (pseudocode-first gate, code_runner usage, debugging guidance, hint ladder); essay: 8 → ~75 lines (claim specificity gate, evidence quality, counter-argument mandate, OutlineTree directive); science: 5 → ~65 lines (observable grounding, no-formulae rule, tool usage, experimental design).
- **12 probes, 3 new assertion helpers** — `assert_no_code_written`, `assert_no_inline_algebra`, `assert_claim_pushed`. New probes: `programming_pseudocode_first`, `math_tool_before_answer`, `essay_claim_specificity`.

**L1 (exhaustive logging)**
- `call_classifier` now emits `llm_classifier` / `llm_classifier_error` JSONL events with query, result, model, latency, tokens.
- `call_summarizer` now emits `llm_summarizer` / `llm_summarizer_error` JSONL events.
- `call_tutor` now adds `user_message_preview` (last user message, 300 chars) to the `llm_call` event.
- `/chat` handler now emits a `chat_turn` event to `backend/logs/chat.jsonl` with phase, hint_level, user_message, agent_reply_preview, tool_called per turn.
- 3 new fast tests in `test_logging.py`.

**U1 (username-first UI)**
- `/persona/create` gains `confirm: bool = False`. New users without `confirm=True` get `status: "confirm_new"` — no session is created.
- `OnboardingView` is now two-step: username → problem. `confirm_new` shows inline confirmation prompt.
- `App.tsx` `persona_session` route no longer holds `pendingQuery`; after persona intake, routes to `{ kind: "onboarding", initialStep: "query" }`.
- 3 new fast tests in `test_persona.py`.

**E1 (wrap-up/reflection improvements)**
- `ThinkingTraceDrawer` now renders a Calibration section (predicted confidence vs. outcome per subproblem) and a Reflections section (question / answer / quality badge).
- `ThinkingTrace` interface in `types.ts` gains `reflection_prompts` and `calibration_points` fields.
- **Known gap**: these sections are empty in real sessions because the agent rarely emits the required signals. Prompt tuning needed.

**126 fast tests pass** (was 115 before the prompt-upgrade milestone; +5 from 17-probe harness expansion).

**T1 (initial-understanding capture + summariser tone — 2026-05-17)**

Fixes the wrap-up "Thinking Trace" diptych: the left-hand "I started thinking…" card, the arrow, and the delta chip never rendered because `session.initial_understanding` was never written. Symptom in the UI was a single right-hand "I ended up here." card with no comparison anchor.

- **Backend capture** — new `_maybe_capture_initial_understanding(session, previous_phase)` in `chat.py` fires at the clarification → next-phase transition (both in `_finalize_turn` and `/session/new`). Idempotent via a `session.initial_understanding is None` guard, so phase clamps don't re-summarise. The capture is deterministic backend-side — it does NOT depend on the agent emitting any signal (sidesteps the same dormancy that still affects `emit_reflection` / `emit_calibration_check`).
- **New summariser** — `call_initial_understanding_summarizer(clarification_student_messages, session_id)` in `llm.py`, mirror of `call_summarizer` plumbing. Cheap classifier model, JSON-object response, fence-stripping, `llm_initial_summarizer` / `llm_initial_summarizer_error` log events, safe `None` fallback on empty input or parse failure.
- **Summariser tone rewrite** — `call_summarizer`'s system prompt rewritten to address the student in second person and forbid graded language ("fragmented", "incomplete", "partial", "shallow"). Replaces the original clinical third-person ("The student understands…") which was rendering as a teacher's report rather than a reflection mirror.
- **`_finalize_turn` is now `async`** — required because the capture call awaits the summariser. Both call sites (`_chat_sse_generator` and the JSON-path `/chat` handler) updated with `await`.
- **No frontend changes** — `TraceHero.tsx` already gated the diptych on `hasInitial && hasFinal` and already declared all four fields in `ThinkingTrace`. Backend populating the field is enough to make the diptych render.
- **Conftest stub for tests** — `fake_openrouter` fixture now monkeypatches `call_initial_understanding_summarizer` to a no-op by default, so existing chat-flow tests don't have to queue an extra LLM response on every clarification exit. Tests that exercise the real capture (in `test_chat_flow.py`) or the real summariser (in `test_llm_client.py`) opt back in with their own monkeypatch.
- **9 new fast tests** — 4 in `test_chat_flow.py` (captures on clarification exit, idempotency, no-fire when still in clarification, thinking-trace surfaces captured value) + 5 in `test_llm_client.py` (happy path, empty input → None, parse failure → None, missing key → None, tone-constraint regression guard).
- **Open: 2 probe failures** — see `PROMPT_ISSUES.md` entries P11.1 (`math_tool_before_answer` — tutor prefers conceptual hint over algebra tool invocation) and P11.2 (`essay_counter_argument_engaged` — assertion phrasing too narrow for valid replies). Neither is a regression from this work; both are pre-existing prompt-or-assertion issues surfaced when the suite was re-run after these changes.

**135 fast tests pass** (+9 from T1; was 126).

---

## Commands

### Backend (`backend/`)

```bash
# install (editable, with dev + math extras) — use the venv
.venv/bin/pip install -e ".[dev,math]"

# run the API (port 8000, no --reload)
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# tests (fast — no LLM calls)
.venv/bin/pytest
.venv/bin/pytest tests/test_llm_client.py -v   # single file
.venv/bin/pytest -k "test_socratic"            # single test by name

# include live-LLM probe tests (slow, costs tokens)
.venv/bin/pytest --run-slow -v

# lint / format
ruff check .
ruff format .
```

Required env vars (see `backend/.env.example`):
- `LLM_MODEL_TUTOR` — main tutor model identifier (OpenRouter)
- `LLM_MODEL_CLASSIFIER` — cheap model for domain detection
- `OPENROUTER_API_KEY`

### Running probes

The probe runner calls `llm.py` directly — the FastAPI server does **not** need to be running.

```bash
cd backend

# run all 17 probes
python -m tests.run_probes

# single probe
python -m tests.run_probes --probe json_schema_compliance

# override model
python -m tests.run_probes --model google/gemini-2.5-flash

# test a prompt variant without restarting the server
python -m tests.run_probes --base-variant base:v2 --domain-variant math:v2
```

Results are appended to `backend/logs/probe_runs.jsonl`. The runner always prints a reply preview for every probe. Bold yellow `[MANUAL]` lines require human judgement — they are never counted in pass/fail.

### Socratic constraints test

```bash
cd backend

# fast canned-reply tests (no LLM calls — always run)
.venv/bin/pytest tests/test_socratic_constraints.py -v

# include live-LLM slow tests (costs tokens)
.venv/bin/pytest tests/test_socratic_constraints.py -v --run-slow
```

### Key env vars

```bash
LLM_MODEL_TUTOR=google/gemini-2.5-flash    # recommended tutor model
LLM_MODEL_CLASSIFIER=qwen/qwen3-6b         # cheap classifier
OPENROUTER_API_KEY=...

TUTOR_TEMPERATURE=0.7                       # default; lower for more deterministic sessions
CLASSIFIER_TEMPERATURE=0.0                  # must be deterministic
PROBE_TEMPERATURE=0.3                       # reproducible probe runs

LOG_LLM_CALLS=true                          # set false in production
PROMPT_VARIANT_BASE=base:v1                 # base prompt folder variant
PROMPT_VARIANT_DOMAIN=math:v2,essay:v1     # per-domain overrides (comma-separated)
```

### Manual session scripts (`probes/`)

`probes/` holds scripted end-to-end sessions for human testers. Each file lists the exact student turns to type verbatim, what to watch for at each turn, pass/fail criteria, and backend log checks. Use these when testing a new prompt or model — they are not automated.

| File | Domain | What it tests |
|---|---|---|
| `probe_01_fence.md` | Math | Fence optimisation — 5 subproblems, algebra + graph tools, escape hatch likely |
| `probe_02_bouncing_ball.md` | Math | Geometric series aha moment — graph convergence, sympy verification |
| `probe_03_essay.md` | Essay | Disengaged student — claim narrowing, counter-argument, no paragraph written |
| `random/test_scenario_bad_explainer.md` | General | Agent under a poor student explainer |
| `random/test_scenario_fizzbuzz.md` | Programming | FizzBuzz — pseudocode first, then translation |
| `random/test_scenario_gaussian.md` | Math | Gaussian integral — advanced; tests graceful degradation |
| `random/test_scenario_skill_gap.md` | Math | Large skill gap — hint ladder stress test |
| `random/test_scenario_tickets.md` | Math | Word problem → system of equations |

### Prompt issues log (`PROMPT_ISSUES.md`)

`PROMPT_ISSUES.md` in the repo root tracks known prompt-level problems (not code bugs). Two open items remain (P6.1: physics classifier routing, P7.4: backend validation rules not yet enforced). The rest are resolved and listed for reference. Check this file before editing any prompt file.

### Temperature

Three independent temperature knobs, all read once at startup:

| Var | Default | Why |
|---|---|---|
| `TUTOR_TEMPERATURE` | `0.7` | Natural variation in Socratic phrasing; too low sounds robotic |
| `CLASSIFIER_TEMPERATURE` | `0.0` | Domain detection must be deterministic |
| `PROBE_TEMPERATURE` | `0.3` | Low but not zero: reproducible probe runs while allowing minor phrasing variation |

### Prompt variants

Prompt variants let you A/B test prompt changes across a server run without touching code.
Variant selection is **static per server process** — restart to switch.

```bash
# switch base Socratic rules to v2 for all sessions
PROMPT_VARIANT_BASE=base:v2 .venv/bin/python -m uvicorn app.main:app ...

# switch math to v2 and essay to v1; other domains use their registered defaults
PROMPT_VARIANT_DOMAIN=math:v2,essay:v1 .venv/bin/python -m uvicorn app.main:app ...
```

Adding a new base variant: create a folder `backend/app/prompts/<version>/` with the same file structure as `v1/`, then add `"base:<version>": _PROMPTS / "<version>"` to `VARIANTS`. Adding a new domain variant: create the prompt file and add its path to `VARIANTS` under `"<domain>:<version>"`. Old keys stay registered so historical probe runs remain reproducible.

### LLM call logs

Every call is written to `backend/logs/llm.jsonl` (and stdout). Set `LOG_LLM_CALLS=false`
to suppress all logging (e.g. in production). The logger is still initialised — only
writes are suppressed, so toggling this at runtime (without restart) works.

`chat_turn` events are mirrored into `llm.jsonl` as well as their own `chat.jsonl`, so
the log viewer sees everything in one file.

### Log viewer

`backend/scripts/view_logs.py` is a local Flask web UI for browsing `llm.jsonl`.

```bash
# install dependency (one-off; already in pyproject.toml)
cd backend && .venv/bin/pip install flask

# launch viewer
cd backend && .venv/bin/python scripts/view_logs.py logs/llm.jsonl

# custom host/port
cd backend && .venv/bin/python scripts/view_logs.py logs/llm.jsonl --host 0.0.0.0 --port 5001
```

Open `http://127.0.0.1:5000`. Features:
- Filter by **session** or **event type** (llm_call, llm_classifier, chat_turn, …)
- Collapsible cards showing thinking / reply / control / signal per turn
- **Refresh Logs** button re-reads the file without restarting the server
- **Readable Export** / **JSONL Export** of selected entries

### Frontend (`frontend/`)

```
# install
npm install

# dev server (port 5173)
npm run dev

# typecheck
npm run typecheck

# production build
npm run build
npm run preview                              # serve the build locally
```

Required env vars (see `frontend/.env.example`):
- `VITE_API_URL` — backend URL (default `http://localhost:8000`)
- `VITE_USE_MOCK` — `true` to use the in-browser mock, `false` to hit the backend

Frontend has no linter configured yet; rely on `tsc` via `npm run typecheck`.

---

## Prompt Architecture

The base prompt is assembled per-turn from a folder of files, not a single flat file. This lets the same `core.txt` be combined with different phase and context blocks without duplicating shared content.

### Folder layout (`backend/app/prompts/v1/`)

| File | When included |
|---|---|
| `core.txt` | Always. Universal Socratic rules, constraints 1–8, structured output contract, math formatting. |
| `phase_clarification.txt` | When `session.phase == "clarification"`. |
| `phase_decomposition.txt` | When `session.phase == "decomposition"`. |
| `phase_solving.txt` | When `session.phase == "solving"`. |
| `phase_wrap_up.txt` | When `session.phase == "wrap_up"`. |
| `block_tool_result.txt` | When the `/chat` request carried a `tool_result` field. |
| `block_calibration.txt` | When an open `CalibrationPoint` exists (prediction given, outcome not yet recorded). |
| `block_reflection_eval.txt` | When a pending reflection has a student response but no quality evaluation yet. |

The domain prompt (`backend/specializations/{domain}/prompt.txt`) is always concatenated after the assembled base.

### Assembly

`load_base_prompt(variant_key, session, had_tool_result)` in `variants.py` reads `core.txt`, then conditionally appends phase and context blocks based on live session state. `chat.py` calls it every turn with the live `Session` object.

In probes and tests, `_load_probe_prompt(domain, phase)` passes a minimal `_PhaseStub` (just `phase` + empty calibration/reflection state) so the correct phase block is included without a real session. `load_combined(domain)` (for tests without any session) calls `load_base_prompt(session=None)` — returns `core.txt` only — then appends the domain prompt.

### Pólya roles across phases

- **Clarification** (`phase_clarification.txt`) — Pólya Step 1. Instructs the agent to use `thinking` to model likely misconceptions before writing any `reply`. Heuristic language must not appear in `reply`.
- **Decomposition** (`phase_decomposition.txt`) — Pólya Step 2 (Devise a Plan). Shapes the questions implicitly; the student names the structure.
- **Solving** (`phase_solving.txt`) — Pólya Steps 2–3. Level-3 hint escalations are Pólya heuristics (working backward, simpler problem, analogy, specialisation, pattern) matched to the student's specific type of stuck-ness. Level 0–2 are pre-heuristic.
- **Wrap-up** (`phase_wrap_up.txt`) — Pólya Step 4 (Look Back). Drives synthesis and surfaces the delta between `initial_understanding` and current articulation.

### Adding a new variant

For a new base variant (e.g. `base:v2`): create `backend/app/prompts/v2/` with the same file structure as `v1/`, add `"base:v2": _PROMPTS / "v2"` to `VARIANTS` in `variants.py`. For a new domain variant: create the file and add its path under `"<domain>:<version>"`. Old keys stay registered so historical probe runs remain reproducible.

### Output schema

Every agent response is a single JSON object with three always-present keys plus an optional `signal` block:

```json
{
  "thinking": "scratchpad — stripped by backend before any processing",
  "reply": "message to student — null when tool_call is set",
  "control": { "phase": "...", "active_subproblem": "...", "hint_level": null, "tool_call": null, "ui_directives": [] },
  "signal": { "subproblem_updates": [], "emit_reflection": "...", ... }
}
```

`signal` is entirely optional — omit the block on quiet turns. `hint_level: null` is a no-op (does not touch the active subproblem's `hints_given` counter). See `core.txt` for the full field-by-field contract and all `signal` fields.

---

## Implementation Notes

Critical findings from the initial implementation pass. Read this before touching the LLM or backend layer.

### Running the servers

**Do not use `--reload` with uvicorn.** The WatchFiles hot-reload caches old `.pyc` files and silently serves stale code. Always do a clean restart:

```bash
# On Linux/Mac — kill running backend and restart
pkill -f "uvicorn app.main" 2>/dev/null; sleep 1
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Always restart the backend after changing any `.py` file or `.txt` prompt.** Temperature and variant env vars are read once at module load — a running server will silently use stale config.

Frontend Vite hot-reload works fine and does not have this problem.

### Python version and venv

The venv is at `backend/.venv/` (Python 3.12). Always use it — never the system Python:

```
backend/.venv/bin/python   ← use for running the server and tests
backend/.venv/bin/pytest   ← must use this, not the system pytest
```

### Environment configuration (`.env`)

Current working configuration in `backend/.env`:

```
OPENROUTER_API_KEY=<key>
LLM_MODEL_TUTOR=google/gemini-2.5-flash
LLM_MODEL_CLASSIFIER=qwen/qwen3.6-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
PERSONA_DIR=./personas
ALLOWED_ORIGINS=http://localhost:5173
LLM_MAX_TOKENS=2048
```

- `LLM_MAX_TOKENS=512` was too low — models need ~300 tokens for the reply + ~200 for the control JSON. Use 2048+.
- `google/gemini-2.5-flash` is the recommended tutor model: free tier, 1M context, reliable instruction-following and JSON output.
- `qwen/qwen3.6-flash` is fast and cheap for the simple classifier task.
- `load_dotenv()` is called in `backend/app/main.py` at startup — `.env` is loaded automatically.

### The `_strip_fences` fix (critical — do not revert)

`backend/app/llm.py` contains `_strip_fences()`, applied to every model response before `json.loads()`. This is essential because `google/gemini-2.5-flash` (and many other models) ignores `json_object` response format and returns markdown prose followed by a ` ```json ` block at the end. Without `_strip_fences`, `json.loads()` fails on every response.

The function uses `re.findall` to collect **all** ` ```json ` blocks and returns the **last** one — because earlier blocks may be math expressions or code examples, not the control JSON.

### Phase transition clamping

The backend clamps illegal phase transitions (e.g. model jumping `clarification → wrap_up`) to the current phase instead of raising HTTP 400. This is in `_validate_phase()` in `backend/app/chat.py`. The original design called for the frontend to soft-retry on 400, but that was not implemented; clamping is the pragmatic v1 fix. A warning is logged so the behaviour is observable.

### Dev persona shortcut

`backend/personas/testuser.json` is pre-created and committed. Using username `testuser` skips the 2-turn LLM-based onboarding entirely (the `/persona/create` endpoint returns `status: "exists"`), making local dev/testing much faster.

### Error visibility

The frontend `api/client.ts` extracts the `detail` field from FastAPI error responses and includes it in the thrown `Error`. `SessionView` catches and displays this as `Error: <detail>` in the chat. This replaced the original generic "Something went wrong" message and is essential for diagnosing backend failures during development.

### LaTeX rendering (MathText component)

All math rendering goes through `frontend/src/components/MathText.tsx` — a thin wrapper around `react-markdown` + `remark-math` + `rehype-katex`. KaTeX CSS is bundled (`import "katex/dist/katex.min.css"` in `main.tsx`), not loaded from CDN.

- `inline` prop: renders math in a `<span>` instead of a `<p>` (prevents nesting block elements inside inline contexts).
- Used in: `ChatPane`, `SubproblemPanel`, `ThinkingTraceDrawer`, `AlgebraSteps`, `RuleRecallPrompt`, `ReflectionPrompt`.
- The algebra backend tool uses `sympy.latex()` (not `str()`) so sympy output renders as proper LaTeX.

For display math (`$$`), the expression must be on its own paragraph with surrounding blank lines — remark-math needs a paragraph boundary to detect block math.

### Algebra tool — implicit multiplication

`backend/specializations/math/tools/algebra.py` uses `sympy.parsing.sympy_parser.parse_expr` with the `implicit_multiplication_application` transform, so expressions like `2x`, `2x+3=7`, `3(x+1)=15` parse correctly. Do **not** revert to bare `sympify()` — it rejects implicit multiplication.

### Tool-call loop fix (critical — do not revert)

`backend/app/chat.py` `_run_chat_turn` has three guards that prevent infinite tool loops:

1. **Unconditional assistant message** — added before the tool result every iteration. Skipping it (e.g. with `if parsed.reply:`) caused the model to see a tool result with no prior assistant message and re-issue the same call.
2. **Same-tool dedup** — if the model calls the same tool twice in a row after already receiving its result, the loop breaks and returns the existing result.
3. **`"role": "user"` for tool result** — Gemini follows instructions in user-role messages more reliably than system-role. The tool result message is sent as `role: "user"` with a `[SYSTEM]` prefix.

### CalibrationCheck + ReflectionPrompt auto-injection (new schema)

The backend auto-injects both widgets in `_build_chat_response`. The model emits only a trigger type; the backend owns the question text.

- Agent emits `signal.emit_calibration_check: true` → backend injects a `CalibrationCheck` directive. The widget question is fixed: `"Before you try — how confident are you that you'll get this right? 1 to 5."` — never model-generated.
- Agent emits `signal.emit_reflection: "trigger_type"` → backend selects a question from `REFLECTION_QUESTIONS[trigger_type]` (defined in `chat.py`) and injects a `ReflectionPrompt` directive. The question is chosen once in `_apply_agent_response` and reused in `_build_chat_response` (via `session.pending_reflection_index`) so the directive and the session record are always consistent.

Both injections deduplicate: if the agent already emitted a directive of that component name in `control.ui_directives`, the backend does not add a second one.

**Phase guard**: if `signal.emit_calibration_check` is true and `control.phase == "wrap_up"` on the same turn, the phase transition is blocked (`parsed.control.phase` is set to `None` before `_validate_phase`).

**Deprecated fields** — `control.calibration_check: str` and `control.reflection_prompt: dict` are kept in `AgentControl` for backward-compat parsing but are no longer read by any handler. If non-None, a debug log warns that the model is emitting old-schema fields. These will be removed once the new-schema probes have validated the model output.

### Structured output schema (current — three top-level keys)

The agent's JSON output has three top-level keys. This is the only valid schema; the old two-key schema (`reply` + `control`) is deprecated.

```json
{
  "thinking": "scratchpad — stripped by backend before any processing",
  "reply": "message to the student (null when tool_call is set)",
  "control": {
    "phase":             "clarification | decomposition | solving | wrap_up | null",
    "active_subproblem": "sp-1 | null",
    "hint_level":        null,
    "tool_call":         { "name": "...", "args": {} } | null,
    "ui_directives":     []
  },
  "signal": {
    "subproblem_updates":      [ { "id": "sp-1", "description": "...", "goal": "...", "status": "..." } ],
    "emit_reflection":         "periodic | self_correction | escape_hatch | wrap_up",
    "last_reflection_quality": "shallow | decent | deep",
    "emit_calibration_check":  true,
    "calibration_outcome":     "correct | wrong | partial",
    "persona_updates":         [ { "field": "...", "operation": "add | remove | set", "value": "...", "evidence": "...", "inferred": true } ],
    "self_correction_noted":   true,
    "escape_hatch_triggered":  true,
    "escape_hatch_reflection": "student's one-sentence account",
    "verification_prompted":   true,
    "concepts_established":    [ "concept name" ],
    "student_question_quality":"surface | probing | insightful",
    "decomposition_source":    "student | tutor",
    "disengagement_noted":     true,
    "refined_query":           "clarified restatement after the framing question"
  }
}
```

Key rules enforced by the backend:

- `thinking` is popped from the raw dict before `AgentResponse.model_validate()` and set to `None` on the parsed object. It never reaches `_apply_agent_response`, `_build_chat_response`, or the frontend.
- `signal` is entirely optional. If absent (quiet turn), `_apply_agent_response` skips all signal handlers — no defaults are written, no errors are raised.
- `hint_level: null` is a no-op — the active subproblem's `hints_given` is not modified. `hint_level: N` (integer) sets it.
- `control.tool_call` non-null + `reply` longer than one sentence → backend retries once with a correction message. Non-fatal if retry fails.
- `subproblem_updates` live in `signal`, not `control`. The deprecated `control.subproblem_updates` field is still parsed but never applied.

`AgentSignal` is defined in `backend/app/chat.py`. `REFLECTION_QUESTIONS` (the trigger → question bank) is also in `chat.py`.

### Phase clamping bug (fixed)

`_apply_agent_response` previously re-applied `session.phase = control.phase` after the caller had already set `session.phase = _validate_phase(...)`. This meant clamped phases (e.g. illegal `clarification → wrap_up`) were silently overwritten with the raw invalid value. Fixed: `_apply_agent_response` no longer touches `session.phase` — the caller owns phase transitions.

### `call_tutor` and `call_classifier` return type

Both return a **2-tuple** `(parsed_output, token_usage)`:

```python
raw_dict, usage = await llm.call_tutor(messages, session_id=session.session_id, temperature=_TUTOR_TEMP)
result, usage   = await llm.call_classifier(query, temperature=_CLASSIFIER_TEMP)
```

`token_usage` shape: `{ prompt_tokens, completion_tokens, total_tokens }`. The `fake_openrouter`
fixture in `conftest.py` patches `_post_chat` (not `call_tutor` itself), so its `Recorder`
does not need to return a tuple — it only needs to accept the `temperature` kwarg.

### One-question threshold (> 2, not > 1)

`assert_one_question_per_turn` fails when a reply contains **more than 2** `?` characters.
This allows parenthetical clarifiers like `"What rule applies here (do you remember it?)"` — two `?`
marks, one question. A reply with 3 or more `?` marks is flagged as stacking questions.
The threshold is consistent across `tests/test_socratic_constraints.py` and `tests/probes.py`.

### Prompt variant system (`backend/app/prompts/variants.py`)

`VARIANTS` maps string keys to `Path` objects. `DEFAULTS` maps role names to their current default
key. `load_prompt(role, variant_key=None)` loads one file. `load_combined(domain, ...)` concatenates
base + domain. `parse_domain_variants(env_value)` parses the comma-separated `PROMPT_VARIANT_DOMAIN`
string into a `dict[domain, variant_key]` — a malformed entry (missing `:`) raises `ValueError` at
startup rather than silently loading the wrong prompt. Old keys stay registered so historical probe
runs against past variants remain reproducible.

### Initial-understanding capture (`backend/app/chat.py`)

`session.initial_understanding` is **not** populated from any agent signal — there is no
`signal.initial_understanding` field. Capture happens server-side in
`_maybe_capture_initial_understanding(session, previous_phase)`, called from `_finalize_turn`
and `/session/new` right after `_validate_phase`. The helper:

1. Returns early if `session.initial_understanding` is already non-None (idempotent).
2. Returns early if the session is still in clarification or never was.
3. Collects the student's clarification-phase user messages from `session.message_history`.
4. Awaits `llm.call_initial_understanding_summarizer(...)`, which returns a one-sentence
   second-person summary (or `None` on parse failure / empty input).
5. Stores the result on the session.

Because the trigger is deterministic, this surface does NOT suffer from the agent-doesn't-emit
dormancy that affects `emit_reflection` / `emit_calibration_check`. If/when those signals are
moved off the agent's hands, this is the pattern to mirror.

### `fake_openrouter` test fixture stubs the initial summariser

`backend/tests/conftest.py`: the `fake_openrouter` fixture monkeypatches
`llm.call_initial_understanding_summarizer` to a no-op (`return None`) by default. Reason: the
clarification → next-phase capture would otherwise consume one extra queued LLM response on
every test that drives a phase transition out of clarification, breaking dozens of existing
chat-flow tests that queue exactly N responses for N expected calls.

Tests that exercise the real capture (e.g. `test_initial_understanding_captured_on_clarification_exit`)
override the stub with their own `monkeypatch.setattr`. Tests that exercise the underlying
function directly (e.g. `test_call_initial_understanding_summarizer_happy_path` in
`test_llm_client.py`) bypass the fixture entirely and patch `_post_chat` themselves.

---

## Decisions (locked in)

The six integration-shape decisions below were debated and confirmed. They are now load-bearing for the rest of this doc — changes to any of them require updating dependent sections in the same PR.

1. **Agent structured output** — single JSON object via OpenRouter structured outputs (JSON Schema mode). Shape: `{ "reply": "...", "control": { ... } }`. Fallback: JSON mode + Pydantic parsing with one retry on parse failure.
2. **Streaming** — Server-Sent Events on `/chat`. Two event types: `token` (chunks of `reply`) and `state` (validated `control` object at end). Non-streaming JSON is the fallback if SSE proves fiddly.
3. **Agent decision authority** — agent owns all phase transitions, hint escalation, subproblem creation, tool calls, mode-specific decisions. Backend is a validator: rejects illegal moves (phase skip, hint jump > +1), never silently overrides; rejection returns an error event the frontend handles as a soft retry.
4. **Domain detection** — runs inside `/session/new` using `query` as input via `LLM_MODEL_CLASSIFIER` (a cheap model, separate from `LLM_MODEL_TUTOR`). `query` is stored as the first user message; `opening_message` is the tutor's first reply, produced in the same call.
5. **Onboarding mechanism** — runs through `/chat` with reserved domain `"persona"` (a specialization at `backend/specializations/persona/`). See "Login & Persona Flow" for the shortened v1 flow.
6. **Username required** on `/session/new`. No anonymous sessions in v1.

---

### Open follow-ups (not blocking v1 build, but decide soon)

- **Type sync between frontend/backend.** Generate `frontend/src/api/types.ts` from FastAPI's OpenAPI schema rather than mirroring by hand. One-time setup, removes a whole class of drift bugs.
- **History truncation.** v1 sends full `message_history` every turn. Acceptable for demos, breaks past ~50 turns. Defer to v2.
- **Frontend lint.** No ESLint/Prettier configured yet. `npm run typecheck` (tsc) is the only frontend gate. Decide whether to add ESLint before deploy or accept tsc-only for v1.

---

## Repository Layout

The repo is split into two top-level project folders that can be developed, run, and deployed independently. They communicate only over HTTP (the contract is the API in "API Endpoints" below).

```
bootcamp-metacognition-project/
├── backend/                    ← Python + FastAPI
│   ├── app/                    ← FastAPI application code
│   │   ├── main.py             ← FastAPI entrypoint, route mounting
│   │   ├── chat.py             ← /chat, /session/new handlers
│   │   ├── persona.py          ← /persona/create, /persona/reset handlers
│   │   ├── session.py          ← in-memory session store + Session model
│   │   ├── plugin_registry.py  ← folder-scanning loader, tool dispatcher
│   │   ├── llm.py              ← OpenRouter client (reads LLM_MODEL env var)
│   │   └── prompts/
│   │       └── socratic_base.txt   ← universal Socratic rules, prepended to every domain prompt
│   ├── specializations/        ← one folder per domain; see "Specialization Plugin System"
│   │   ├── math/
│   │   ├── programming/
│   │   ├── essay/
│   │   ├── science/
│   │   └── general/
│   ├── personas/               ← runtime persona JSON files (gitignored except .gitkeep)
│   ├── tests/
│   ├── pyproject.toml          ← or requirements.txt — pin during scaffold
│   └── .env.example            ← LLM_MODEL, OPENROUTER_API_KEY, etc.
│
├── frontend/                   ← React + Vite + Tailwind
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                ← typed client for the backend API contract
│   │   │   ├── client.ts       ← fetch wrapper, base URL from VITE_API_URL
│   │   │   ├── types.ts        ← mirrors backend schemas (Session, Subproblem, ThinkingTrace, Persona)
│   │   │   └── mock.ts         ← in-browser mock that satisfies the contract; toggle via VITE_USE_MOCK
│   │   ├── components/         ← domain-agnostic: ChatPane, SubproblemPanel, ToolPane, HintBadge, ConfidenceWidget, ThinkingTraceDrawer
│   │   ├── specializations/    ← domain-specific UI components + frontend tool handlers, mirrored 1:1 with backend/specializations/
│   │   │   ├── registry.ts     ← maps "<domain>.<component>" → React component, and "<domain>.<handler>" → frontend tool handler
│   │   │   ├── math/           ← AlgebraSteps.tsx, GraphView.tsx
│   │   │   ├── programming/    ← CodeOutput.tsx, PseudocodePad.tsx, handlers/PyodideRunner.ts
│   │   │   ├── essay/          ← OutlineTree.tsx
│   │   │   └── science/        ← GraphView.tsx, DataTable.tsx
│   │   ├── views/              ← OnboardingView, SessionView, WrapUpView
│   │   └── styles/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.example            ← VITE_API_URL, VITE_USE_MOCK
│
├── reflections/                ← team journals, NOT code (ignore for engineering tasks)
└── CLAUDE.md
```

### Cross-cutting rules

- The **API contract** in this file (see "API Endpoints") is the integration boundary between `frontend/` and `backend/`. Contract changes require updating both sides plus this doc in the same change — otherwise the frontend mock and the backend diverge.
- Frontend never imports from `backend/` and vice versa. Shared shapes are mirrored by hand in `frontend/src/api/types.ts`; if schemas drift, fix `types.ts` from this CLAUDE.md.
- The frontend must work standalone against `VITE_USE_MOCK=true` so UI work isn't blocked by backend progress.
- A **specialization is a pair**: `backend/specializations/<domain>/` (prompt, tools, manifest) AND `frontend/src/specializations/<domain>/` (React components the agent can ask to render). The two halves are coupled by names declared in `manifest.json`'s `ui_components` list — see "Specialization UI Contract" below. Adding a new domain means landing both folders together.
- The frontend discovers domains and their component catalog via `GET /specializations`; it must not hardcode domain names. Components are looked up by `"<domain>.<component_name>"` through `frontend/src/specializations/registry.ts`.
- The frontend must work standalone with `VITE_USE_MOCK=true`. The mock layer must emit the same `ui_directives` shape a real backend would, so component rendering is exercised in mock mode too.
- Paths shown elsewhere in this doc (e.g. `app/prompts/socratic_base.txt`, `personas/{username}.json`, `specializations/math/prompt.txt`) are relative to `backend/` unless prefixed with `frontend/`.

---

# Aporeka

> **Core philosophy**: The AI never solves the problem for the student.
> It guides them to solve it themselves by surfacing their own understanding,
> decomposing the problem collaboratively, and nudging — never telling.

> **Design thesis**: In an AI-rich world, the ability to frame problems, judge
> outputs, and monitor one's own thinking matters more, not less. Every feature
> of this app should strengthen one of those behaviours — not shortcut it.
> Students learn by doing: through decision-making, decomposition, and reflection.
> Never by reading tips or watching the AI perform.

---

## Project Overview

A web-based learning tool for **teenagers (roughly 13–18)** that strengthens thinking skills which stay valuable in an AI-rich world: framing problems, checking understanding, calibrating confidence, reflecting on mistakes, and **judging AI outputs**. Built for the [Metacognition Vibe Coding Task](https://docs.tk.sg/Metacognition-Vibe-Coding-Task-551dd9d8b64483d7942101e280188fdb).

The product is one loop in v1, with a second loop designed and deferred:

1. **Solving Mode (v1)** — student brings a school-level problem (algebra, intro programming, essay outline). A Socratic tutor agent guides them to construct the solution themselves, never giving the answer. The "show and do, don't tell" mandate from the brief lives here.
2. **Critique Mode (post-v1, designed but not built)** — student brings an AI-generated artifact and a Critic-Coach agent guides them to evaluate it. This is the "judging AI outputs" axis the brief asks for. Full design lives in "The Critique Loop" below and in `backend/app/prompts/critic_base.txt`; we ship Solving Mode first and add Critique Mode in a follow-up release.

The session schema, plugin system, and thinking-trace surface are designed to accommodate both modes from day one — `mode` is on the session, the SSE protocol carries both base prompts' control shapes, and `critic_base.txt` is already drafted. The deferral is execution, not architecture. Once Solving Mode is stable in production, adding Critique Mode should be additive rather than disruptive.

**Target audience constraints**:
- Examples and tone calibrated for teens (school subjects, not undergraduate).
- Short onboarding (2 questions max) to lower drop-off; remainder of the persona is captured passively from conversation.
- Engagement loop matters: visible progress, agency in mode/domain choice, a thinking trace at the end that feels like a reward not a report card.

**Current scope (v1)**:
- Solving Mode only. Critique Mode is designed and prompt-drafted (`critic_base.txt`) but deferred to v1.1.
- Three specializations as MVP: `math` (school-level algebra, arithmetic, basic geometry), `programming` (intro Python with Pyodide-based browser runner), `essay` (paragraph-level argumentation, no tools). `science` and `general` remain scaffolded but not MVP.
- Periodic reflection prompts + end-of-session thinking trace
- Calibration tracking (predict-then-check)
- Persona persistence per username, JSON files on disk
- Deployed on the team's AWS EC2 instance (see "Deployment")
- No auth tokens, no cloud DB, no cross-session learning

---

## Login & Persona Flow

**Design intent**: get the student into a productive session as fast as possible. Onboarding asks the minimum, then the rest of the persona is **inferred passively** from how they talk during early sessions. Long form-based intake kills teen drop-off; this product never has one.

### Onboarding flow (v1)

1. User enters a username (no password — this is identity, not auth).
2. App checks `backend/personas/{username}.json`. If it exists → skip to session.
3. If not: a 2-turn welcome runs via `/chat` against the reserved `"persona"` domain:
   - Turn 1: "Hey, before we dive in — what's your age or school year?" *(Captures: age band, school level)*
   - Turn 2: "Cool. What brings you here today — a specific problem, or just exploring?" *(Captures: initial intent, anchors the first session)*
4. The persona agent writes a **stub persona** (age band + initial intent + `created_at` only) and routes the student into the first real session.
5. From that session onward, every `/chat` response may include a `control.persona_updates` block that merges into the persona file: inferred education level (from problem complexity), inferred confident/difficult subjects (from which domains they pick and how they handle them), inferred learning style (from which hint levels land vs. miss). Fields gain an `inferred: true` flag when set this way.

The persona file is therefore **partial on day 1 and grows**. The system prompt always notes which fields are inferred vs. asked, so the agent treats inferred signals as hypotheses, not facts.

### Persona JSON schema (`backend/personas/{username}.json`)

```json
{
  "username": "alex",
  "created_at": "2026-05-14T00:00:00Z",
  "age_band": "13-15 | 16-18 | other",
  "school_level": "lower_secondary | upper_secondary | other",
  "initial_intent": "free-form sentence from onboarding turn 2",
  "education_detail": { "value": "year 10", "inferred": false },
  "confident_subjects": [{ "value": "linear equations", "inferred": true, "evidence": "solved sp-1 of session abc without hints" }],
  "difficult_subjects": [{ "value": "word problems", "inferred": true, "evidence": "escape hatch used twice in session abc" }],
  "learning_style": { "value": "examples_first", "inferred": true },
  "preferred_pace": { "value": "medium", "inferred": true },
  "goals": { "value": "pass next math test", "inferred": false }
}
```

Convention: fields captured at onboarding (`age_band`, `school_level`, `initial_intent`) and metadata (`username`, `created_at`) are flat strings — they are direct answers from the student, not inferences. Every other field is `{ value, inferred, evidence? }` so the agent can flag inferred values as hypotheses. The agent reads inferred fields with appropriate uncertainty ("I've noticed you seem comfortable with X — does that feel right?") and can ask a confirming question to upgrade `inferred: true → inferred: false`.

### Persona injection (per session)

```python
def build_prompt(session: Session, user_message: str) -> list[dict]:
    persona_ctx = f"Student profile:\n{session.persona.to_context_str()}" if session.persona else ""
    return [
        {"role": "system", "content": SOCRATIC_BASE + DOMAIN_SYSTEM_PROMPTS[session.domain]},
        {"role": "system", "content": persona_ctx},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
        {"role": "user", "content": user_message}
    ]
```

`persona.to_context_str()` returns a short natural-language summary:
> *"The student is a 2nd-year CS undergraduate. Confident in linear algebra and Python. Finds probability and recursion difficult. Prefers examples before theory. Goal: prepare for algorithms exam."*

### Persona update (optional, v1)

A `/persona/reset` route clears the file and reruns onboarding. No in-session updates in v1.

### Storage

- Personas stored as JSON files in `backend/personas/` (server-side; gitignored).
- No encryption in v1 — no sensitive data is collected.
- Username is the only identifier; no passwords, no email.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) + Tailwind |
| Backend | Python + FastAPI |
| LLM routing | OpenRouter (model-agnostic; no model hardcoded — set via `LLM_MODEL` env var) |
| Tool execution | FastAPI endpoints (algebra CAS, code runner, graphing) |
| Session state | In-memory (server-side, keyed by session ID) |
| Auth | None (v1 — simple username entry for persona persistence) |

---

## Architecture

The frontend and backend are independent projects. Their only coupling is HTTP — see "API Endpoints".

```
frontend/  (React + Vite + Tailwind, port 5173)
  Browser
   │
   ├── ChatPane            ← primary interaction surface
   ├── SubproblemPanel     ← decomposition tree, built collaboratively
   ├── ToolPane            ← renders tool output for whichever specialization is active
   └── ThinkingTraceDrawer ← session reflection (shown at end)
        │
        │  HTTP (VITE_API_URL → http://localhost:8000 in dev)
        │  ── or ── in-browser mock when VITE_USE_MOCK=true
        ▼
backend/  (Python + FastAPI, port 8000)
  app/
   ├── POST /chat                          ← main message relay, carries session state
   ├── POST /session/new                   ← initialise session, detect domain
   ├── POST /tools/{tool_name}             ← generic tool dispatch (routes to registered plugins)
   ├── GET  /session/{id}/thinking-trace   ← return session reflection object
   ├── POST /persona/create | /persona/reset
   └── GET  /specializations               ← discovery: lists registered domains + tools
        │
        ▼
backend/specializations/  (Plugin Registry — folder-scanned at startup)
   ├── math/           ← registers: algebra (sympy), graph (matplotlib)
   ├── programming/    ← registers: code_runner (sandboxed exec)
   ├── essay/          ← registers: (no tools in v1; prompt-only)
   ├── science/        ← registers: graph, data_table
   └── [future]/       ← drop a new folder in, register tools + prompt, done
        │
        ▼
OpenRouter  →  configured model via LLM_MODEL env var (teaching persona)
              (tool calls invoke registered plugin endpoints)
```

---

## Session State Schema

Kept server-side, passed back to LLM as context on each turn.

```json
{
  "session_id": "uuid",
  "mode": "solving | critique",
  "domain": "math | programming | essay | science | general",
  "original_query": "...",
  "artifact": null,
  "phase": "clarification | decomposition | solving | critique | synthesis | wrap_up",
  "initial_understanding": "student's articulated understanding (captured in clarification phase)",
  "initial_critique": null,
  "subproblems": [
    {
      "id": "sp-1",
      "description": "...",
      "goal": "what the student says this part should achieve",
      "status": "pending | active | solved",
      "hints_given": 0,
      "direct_answer_requested": false,
      "escape_hatch_reflection": null,
      "confidence_score": null
    }
  ],
  "active_subproblem_index": 0,
  "critique_findings": [
    { "id": "f-1", "claim": "student-stated issue with the artifact", "kind": "factual_error | reasoning_gap | missing_step | overconfident_language | other", "verified": false }
  ],
  "calibration_points": [
    { "subproblem_id": "sp-1", "predicted_confidence": 4, "outcome": "correct | wrong | partial", "noted_at": "iso8601" }
  ],
  "reflection_prompts": [
    { "trigger": "periodic | self_correction | escape_hatch | wrap_up", "question": "...", "response": "...", "quality": "shallow | decent | deep | null" }
  ],
  "persona_updates_pending": [],
  "metrics": {
    "turns_total": 0,
    "clarification_turns": 0,
    "decomposition_turns": 0,
    "hints_per_subproblem": [],
    "direct_answer_requests": 0,
    "self_corrections": 0,
    "phase_timestamps": {}
  }
}
```

- `mode` is fixed at `/session/new` and never changes within a session.
- `domain` is one of the five user-facing specializations above. The `persona` specialization is a reserved internal domain used only for onboarding sessions — it is never returned by the classifier, never user-selectable, and the `internal: true` flag in its `manifest.json` excludes it from `GET /specializations`.
- `artifact` is the AI-generated content under critique; only populated when `mode = critique`. Either the student pastes it, or the system generates it (see Critique Loop).
- `phase` set differs by mode (see Modes below).
- `critique_findings` are issues the student names; `verified` flips when the critic-coach agrees the issue is real after Socratic probing.
- `calibration_points` are predict-then-check records — see Reflection & Calibration subsystem.
- `reflection_prompts` records every reflection the agent asks for, the student's answer, and the agent's later quality assessment of that answer.

---

## Modes

A session is in one of two modes, fixed at creation time. Both share the same `/chat` plumbing, plugin system, and thinking-trace surface; the agent's system prompt and phase sequence change. **In v1 only Solving Mode is shipped**; Critique Mode is fully specified below and prompt-drafted, scheduled for v1.1.

### Solving Mode (v1)
The student brings a problem; the agent guides them to construct the solution. Phase sequence: `clarification → decomposition → solving → wrap_up`. The Socratic loop documented below.

### Critique Mode (deferred to v1.1)
The student brings (or asks the system to generate) an AI artifact — a worked solution, an essay paragraph, a code snippet — and the agent guides them to evaluate it. Phase sequence: `clarification → critique → synthesis → wrap_up`. This is the "judge AI outputs" axis the brief calls for. Full description in "The Critique Loop" section. Implemented when v1 is stable in production.

In v1 the frontend shows only the "Bring a problem" entry path. The `mode` field on sessions defaults to `"solving"` and is the only valid value the v1 API accepts. The "Bring something an AI wrote" + "Let the AI try first" entries land with critique.

---

## The Solving Loop (CRITICAL — core of the product)

This is the heart of the app. Every design decision should serve this flow.

### Phase 0 — Domain Detection (automatic, 1 LLM call)

On the first user message, a fast classification call determines:
- `domain`: math | programming | essay | science | general
- `complexity_hint`: single-step | multi-step | open-ended

This selects the **domain system prompt** and the available **UI components**. (The `persona` specialization is reserved for onboarding only — never returned by the classifier and never user-selectable; see the note in "Session State Schema".)

---

### Phase 1 — Clarification (student articulates understanding first)

**Rule**: The AI does NOT engage with the problem until the student has stated their own understanding.

System prompt instruction:
```
You are a Socratic tutor. The student has just submitted a problem.
Do NOT attempt to solve it or hint at the solution.
Ask 1–2 targeted questions to surface what the student already understands
about this problem. Wait for them to answer before proceeding.
Capture their response as their "initial_understanding".
```

The AI should ask things like:
- *"Before we dig in — what's your current thinking on this? Even a rough intuition is fine."*
- *"What part feels clear to you right now, and what feels murky?"*
- *"Have you seen a problem like this before? What did you try?"*

**Exit condition**: Student has articulated some initial understanding (even "I have no idea where to start" is valid — note it and move on).

---

### Phase 2 — Collaborative Decomposition

**Rule**: The AI never lists the subproblems. It nudges the student to identify them.

System prompt instruction:
```
The student has stated their initial understanding. Now help them decompose
the problem into meaningful parts. Do NOT enumerate the subparts yourself.
Ask questions that help the student discover the natural sub-structure:
- "What would you need to figure out first before you can tackle the whole thing?"
- "If you solved this smaller piece, how would that help with the rest?"
- "Can you break this into steps? What's the first step you'd take?"
Accept each part the student proposes. Ask them to state the *goal* of each part
(what does solving it achieve?). Build the subproblem list from their responses.
When the student seems satisfied with the breakdown, confirm it and move to solving.
```

**UI**: The `SubproblemPanel` renders the decomposition tree live as the student proposes parts. Each node shows: description, goal, status.

**Exit condition**: Student confirms the decomposition (or AI gently suggests they may be missing a key piece via a question, never a statement).

---

### Phase 3 — Solving Loop (per subproblem)

For each subproblem, in order:

#### 3a. Activation
- AI announces the active subproblem and asks the student to attempt it.
- *"Okay, let's work on [sp-1]. What's your first instinct here?"*

#### 3b. Hint Ladder (escalating nudges)
Each wrong turn or "I'm stuck" gets a hint, not an answer. Hints escalate:

| Hint Level | Style |
|---|---|
| 1 | Conceptual question (*"What does X mean in this context?"*) |
| 2 | Reframe (*"What if you thought about it as…?"*) |
| 3 | Point to a foundational concept (*"Do you remember how [relevant concept] works?"*) |
| 4 | Worked analogy (*"Here's a similar but simpler case — does this help?"*) |
| 5 | Near-direct (*"You're very close. The key insight is [vague direction]."*) |

Hint level is tracked in session state (`hints_per_subproblem`).

#### 3c. Tool Offload (mechanical sub-tasks)
When a subproblem requires:
- **Algebra / symbolic manipulation** → call `/tools/algebra` (sympy), show steps in ToolPane
- **Graphing** → call `/tools/graph`, render in ToolPane, let student interpret
- **Code execution** → invoke the `code_runner` tool (runs in the browser via Pyodide; see "Generic tool dispatch"), show output in `CodeOutput`, ask student to interpret it
- **Standard algorithm** → provide the implementation via tool, ask student to explain what it does

The AI never presents tool output as "the answer." It presents it as data for the student to reason about.

#### 3d. Confidence Check (after each subproblem)
When a subproblem is resolved:
- *"How confident are you in this solution? 1–5?"*
- *"Is there anything about this step you're still unsure about?"*
- *"Could you explain why this works to someone else?"*

Low confidence → one more round of questions before moving on.

#### 3e. Soft Escape Hatch (direct answer, rare)
If the student explicitly asks for the answer multiple times, or signals strong frustration:

1. First: *"I can tell you're stuck. Do you want a strong hint, or do you want me to just show you this step?"*
2. If they confirm "just show me": **before giving the answer**, ask them to write one sentence: *"Before I show you — in one sentence, where exactly did your thinking get stuck?"*
3. Store their response as `escape_hatch_reflection` in the thinking trace.
4. Then provide the answer for *that subproblem only* and continue the loop.

**Why the reflection step matters**: it turns the failure mode into a metacognitive moment. The student practises noticing their own stuck-point, which is the skill the app is building. It also makes the escape hatch feel earned rather than cheap. Never skip this step — even if the student resists, prompt once more before proceeding.

The answer is never offered proactively. Escape hatch is per-subproblem only.

---

### Phase 4 — Wrap-Up

After all subproblems are solved:
1. AI asks the student to synthesize: *"Can you now explain the full solution in your own words?"*
2. Compare their current explanation to their `initial_understanding` — surface the delta.
3. Generate session metrics summary (see Metrics section).

---

## The Critique Loop (deferred to v1.1 — design retained)

This is the second teaching loop and the product's strongest answer to the brief's "judge AI outputs" directive. **Not in v1; scheduled for v1.1.** The design and prompt (`critic_base.txt`) are retained because the architecture below (session `mode`, artifact field, critique-specific control schema, frontend panels) was built into v1 to make this an additive rather than disruptive addition later.

Same Socratic discipline as Solving, inverted: the AI produces or imports the content; the student evaluates it.

### Setup

A critique session starts with an `artifact` — a worked AI solution, an essay, a code snippet, an explanation. Two ways it gets there:

- **Imported**: student pastes content they got from another AI (ChatGPT, school chatbot, classmate's GPT use) into the input on the landing screen.
- **Generated**: student types a prompt ("solve this differential equation", "write a paragraph arguing X"), and the backend calls a **separate, non-Socratic LLM** (`LLM_MODEL_ARTIFACT`, may be the same as `LLM_MODEL_TUTOR`) to produce the artifact. The system prompt for this call is *not* the Socratic base — the goal is to produce realistic AI output, including realistically subtle errors. The artifact may be deliberately seeded with one or two introduced flaws via a secondary editing pass (v2; v1 takes the LLM's first response unmodified).

The artifact is stored in `session.artifact` and shown to the student in a dedicated `CritiqueArtifactPanel` on the left. The right side is the chat with the Critic-Coach.

### Phase C0 — Initial Read (silent first impression)

Before the coach engages, the student is asked for an `initial_critique` — one sentence: *"On first read, what's your gut feeling about this?"* This anchors a comparison at wrap-up, parallel to `initial_understanding` in solving.

### Phase C1 — Clarification

The coach asks the student to articulate what the artifact is *claiming*. Many critique failures happen because the student didn't parse the claim carefully. *"In your own words, what is this trying to convince you of?"* Captures their understanding before they evaluate.

### Phase C2 — Critique (per finding, escalating depth)

The student names issues; each becomes a `critique_finding`. For each finding:

**C2a. Surface the finding.**
The student says what they think is wrong. The coach **never confirms or denies on the spot**. *"Walk me through where you see that. What specifically in the text gave you that read?"*

**C2b. Test the finding (the key Socratic move).**
The coach probes: *"What would you expect to see if this part were correct?"* / *"Could there be a version of this where what they wrote is right?"* / *"How would you check?"* The student either strengthens the finding (verified = true) or retracts it (a self-correction — celebrated, noted in metrics).

**C2c. Tool offload when applicable.**
For math critiques, the coach may invoke the algebra tool to actually evaluate a step the student suspects. For code critiques, invoke the code runner on a suspicious section. Tool output is data, not verdict — the student interprets it.

**C2d. Coverage check.**
After the student says they're done, the coach asks once: *"Anything in this artifact you didn't look at carefully?"* This is the only place the coach may gently surface an issue the student missed — and only as a question, never as a statement. (*"What do you make of the third paragraph's claim about X?"* not *"They got X wrong."*)

Hint ladder applies as in Solving: if the student is stuck on a finding (says "I dunno, something feels off"), the coach escalates by exactly one level per turn. Level 5 is *"have a closer look at [vague region]"* — never *"here's the bug."*

### Phase C3 — Synthesis

The student writes their final verdict on the artifact: *"In two or three sentences, what would you tell someone who was about to trust this?"* This `final_critique` is the analog of `final_understanding` in solving. The coach compares it to `initial_critique` — the delta is the learning.

### Phase C4 — Wrap-Up

Same as Solving's wrap-up: thinking-trace summary, but framed around critique quality:
- *"You found N issues in this artifact. You retracted M of them after looking closer — that's calibration, not failure."*
- *"At first you said: '[initial_critique]'. After working through it: '[final_critique]'. That shift is the skill."*
- *"You missed [issue Z]. Worth knowing for next time — but you also caught [issue Y], which most people gloss over."*

### Constraints on the Critic-Coach (must be in its base prompt)

- **Never declare the artifact correct or incorrect overall.** Critique is per-claim; the synthesis is the student's call.
- **Never name an issue the student hasn't approached.** Coverage check is the only exception, and only as an open question.
- **Praise specifically.** "Good catch on the units" beats "great job." Teen calibration matters here.
- **Self-corrections are wins.** A retracted finding is the metacognitive skill firing correctly; reflect that warmly back.

---

## Specialization Plugin System

Each domain (math, programming, essay, science, etc.) is a **self-contained plugin** — a folder that registers its own system prompt, tools, and UI components. The core app has zero knowledge of any specific domain. Adding a new specialization requires no changes to core code.

### Plugin folder structure

All plugins live under `backend/specializations/`:

```
backend/specializations/
  math/
    __init__.py          ← registers the plugin
    prompt.txt           ← domain system prompt (Socratic core auto-prepended)
    tools/
      algebra.py         ← sympy CAS tool
      graph.py           ← matplotlib render tool
    manifest.json        ← declares tool names, descriptions, UI hints
  programming/
    __init__.py
    prompt.txt
    manifest.json        ← code_runner is a frontend tool (Pyodide); no backend tool files
  essay/
    __init__.py
    prompt.txt
    manifest.json        ← no tools in v1
  science/
    __init__.py
    prompt.txt
    tools/
      graph.py           ← shared impl (symlinked or copied from math/)
      data_table.py
    manifest.json
```

### manifest.json schema

```json
{
  "domain": "math",
  "display_name": "Mathematics",
  "complexity_hints": ["single-step", "multi-step", "open-ended"],
  "tools": [
    {
      "name": "algebra",
      "description": "Symbolic algebra via sympy",
      "execution": "backend",
      "endpoint": "/tools/algebra",
      "ui_component": "AlgebraSteps",
      "input_schema": {
        "expression": "string",
        "operation": "simplify | solve | diff | integrate"
      }
    },
    {
      "name": "graph",
      "description": "Plot a mathematical expression",
      "execution": "backend",
      "endpoint": "/tools/graph",
      "ui_component": "GraphView",
      "input_schema": {
        "expression": "string",
        "x_range": "[number, number]",
        "variables": "object"
      }
    },
    {
      "name": "code_runner",
      "description": "Run a Python snippet in the browser via Pyodide and return stdout/stderr/value",
      "execution": "frontend",
      "frontend_handler": "PyodideRunner",
      "ui_component": "CodeOutput",
      "input_schema": {
        "code": "string",
        "stdin": "string?"
      }
    }
  ],
  "ui_components": [
    {
      "name": "AlgebraSteps",
      "description": "Step-by-step rendering of symbolic manipulation output from the algebra tool.",
      "props_schema": {
        "steps": "Array<{ expr: string, rule: string }>",
        "final": "string"
      },
      "trigger": "tool_result"
    },
    {
      "name": "GraphView",
      "description": "Renders a plot from a backend-rendered PNG or inline SVG.",
      "props_schema": {
        "image_url": "string",
        "caption": "string?"
      },
      "trigger": "tool_result"
    },
    {
      "name": "RuleRecallPrompt",
      "description": "Inline card asking the student to state which rule applies before any algebraic step. Domain-specific Socratic widget.",
      "props_schema": {
        "candidate_rules": "string[]",
        "context_expr": "string"
      },
      "trigger": "agent_directive"
    }
  ]
}
```

Each tool entry declares `execution: "backend" | "frontend"`. Backend tools also declare `endpoint` (where the backend dispatches the call internally). Frontend tools also declare `frontend_handler`, naming the TypeScript handler under `frontend/src/specializations/<domain>/handlers/` that the client invokes when the `frontend_tool` SSE event fires. See "Generic tool dispatch" for the runtime flow.

`tools[].ui_component` and entries in `ui_components` must reference the **same name** the frontend exports from `frontend/src/specializations/<domain>/`. The frontend's `registry.ts` maps `"<domain>.<ComponentName>"` to a React component. Names not present in the registry cause the frontend to log a warning and render a fallback — the chat itself must still proceed.

`trigger` declares when a component appears:
- `tool_result` — rendered by `ToolPane` after a `/tools/{name}` call returns
- `agent_directive` — rendered inline (or in a side panel) when the agent emits a `ui_directive` in its `/chat` response (see "Specialization UI Contract")

### Plugin registration (Python)

```python
# backend/specializations/math/__init__.py
from app.plugin_registry import register_specialization

register_specialization(
    domain="math",
    prompt_file=__file__,           # resolved relative to this folder
    tools=["algebra", "graph"],
)
```

### Generic tool dispatch

Tools declare an `execution` field in their manifest. Two paths:

**Backend tools** (`execution: "backend"`) — server-side. The backend invokes the tool when the agent emits `control.tool_call`, and replays the result into the next turn's context. Direct invocation from the frontend goes through:

```
POST /tools/{tool_name}
  body: { session_id, ...tool-specific args }
  returns: { result, ui_component, display_data }
```

**Frontend tools** (`execution: "frontend"`) — browser-side. Used for sandboxed code execution (Pyodide) and anything else better kept off the server. Flow:

1. Agent emits `control.tool_call = { name: "code_runner", args: { ... } }` as usual.
2. Backend recognises `execution: "frontend"` and forwards the call by emitting an `event: frontend_tool` on the SSE stream with `{ "name": "code_runner", "args": { ... } }`. The `state` event still contains the agent's full `control` object — both events fire on the same turn, but `frontend_tool` is the imperative the client dispatches on.
3. Frontend dispatches to the `frontend_handler` named in the manifest (e.g. `PyodideRunner`), captured in `frontend/src/specializations/<domain>/handlers/`.
4. Result is sent back to the backend via `POST /chat` with a new body field: `tool_result: { name, result, display_data }`. The backend stores this in the session and replays it to the agent on the next LLM call.
5. The matching `ui_component` (e.g. `CodeOutput`) renders the result in the `ToolPane`.

This keeps the agent's protocol uniform (it always emits `tool_call`) while letting execution happen wherever it's safest. The student never sees the difference.

For the Python code runner specifically: Pyodide loads lazily on first use, runs each snippet in a fresh execution context, and times out after 5 seconds. Available standard library is whatever Pyodide ships (sufficient for school-level intro Python).

The LLM never calls a hardcoded endpoint. It picks from the tool list injected into its system prompt by the active plugin.

### Specialization UI Contract

A specialization can ask the frontend to render its own React components in two ways:

**1. Tool results** — when the agent calls a tool, the tool's response carries a `ui_component` name and a `display_data` payload. The frontend looks up `<domain>.<ui_component>` in `registry.ts` and renders it inside the `ToolPane`. This is the existing flow.

**2. Agent directives** — the agent can ask the frontend to render a domain-specific widget *without* a tool call, by emitting a `ui_directives` array in its `/chat` response. This is how specializations attach Socratic widgets (e.g. a "pick the rule that applies" card, a confidence slider tied to a concept, a pseudocode pad).

Extended `/chat` response shape:

```json
{
  "reply": "Before we simplify, which rule applies here?",
  "phase": "solving",
  "subproblems": [ ... ],
  "ui_directives": [
    {
      "component": "RuleRecallPrompt",
      "domain": "math",
      "props": {
        "candidate_rules": ["distributive", "associative", "commutative"],
        "context_expr": "3(x + 2)"
      },
      "placement": "inline | side_panel | modal",
      "lifetime": "until_dismissed | until_next_turn | persistent_in_subproblem"
    }
  ]
}
```

Rules:

- The agent **may not bypass the Socratic rules through UI** — a `RuleRecallPrompt` may surface candidate answers, but its props must not contain the correct answer, hint level, or completed work. Treat directives the same as chat text: they ask, they don't tell.
- The frontend treats `ui_directives` as advisory. If `component` isn't in the registry for that `domain`, log a warning and continue — the conversation must never break because a widget is missing.
- `placement: inline` renders inside `ChatPane` attached to the message. `side_panel` opens `ToolPane`. `modal` blocks the chat until dismissed (use sparingly; reserve for high-friction moments like the escape-hatch reflection gate).
- `lifetime` decides when the frontend removes the widget. `until_next_turn` is the default for transient prompts; `persistent_in_subproblem` for widgets that should stay alive while a subproblem is active.
- User interaction with a widget is sent back as the next `/chat` message — the body grows a `directive_response` field: `{ message?, directive_response?: { component, value } }`. The agent reads the value and continues the Socratic loop.

Backend prompt guidance for emitting directives lives in each domain's `prompt.txt`. The Socratic base prompt should remind the model: *"You may emit `ui_directives` to elicit structured input from the student, but never to deliver answers or hints beyond your current escalation level."*

### Adding a new specialization (checklist)

Backend half (`backend/specializations/{domain}/`):
1. Create the folder.
2. Write `prompt.txt` (Socratic rules auto-prepended). Include guidance on when to emit `ui_directives`.
3. Implement any backend tools in `tools/` (or reuse existing ones via import). Skip this if all tools are frontend (`execution: "frontend"`).
4. Write `manifest.json` — declare `tools` (each with `execution: "backend" | "frontend"`; frontend tools also declare `frontend_handler`) and the full `ui_components` catalog.
5. Register in `__init__.py`.

Frontend half (`frontend/src/specializations/{domain}/`):
6. Create the folder.
7. Implement one `.tsx` component per entry in the manifest's `ui_components` list, with the declared props shape.
8. If any tool has `execution: "frontend"`, implement its handler at `frontend/src/specializations/<domain>/handlers/<HandlerName>.ts` and register it in `registry.ts` under the `"<domain>.<HandlerName>"` key.
9. Export components from an `index.ts` and add entries to `frontend/src/specializations/registry.ts` keyed `"<domain>.<ComponentName>"`.

The domain then appears automatically in detection, routing, and the `/specializations` discovery endpoint. No changes to `/chat`, `/session/new`, or any other specialization. If only the backend half is landed, the frontend renders a fallback when directives reference unknown components — work in progress is safe to merge.

---

## Domain System Prompts

Each specialization's `prompt.txt` extends the Socratic core (which is always prepended). The Socratic base enforces the universal rules (one question at a time, never enumerate subproblems, etc.).

### Mathematics (`backend/specializations/math/prompt.txt`)
```
You are a maths tutor. When the student needs to see symbolic work, invoke the
algebra tool — do not compute by hand in the chat. When a visual would help,
invoke the graph tool. Never simplify expressions for the student unless they
have attempted it first. Ask "what rule applies here?" before any algebraic step.
```

### Programming (`backend/specializations/programming/prompt.txt`)
```
You are a programming tutor. Do not write code for the student. Ask them to
write pseudocode first. When they have working pseudocode, help them translate
it. Use the code runner to test their implementations, then ask them to explain
the output. For bugs, ask "what do you expect this line to do?" before pointing
at the error.
```

### Essay / Writing (`backend/specializations/essay/prompt.txt`)
```
You are a writing coach. Do not draft any part of the essay for the student.
Help them build an outline by asking about their argument and evidence.
For each paragraph, ask "what is the one thing this paragraph must prove?"
```

### Science (`backend/specializations/science/prompt.txt`)
```
You are a science tutor. Ground every concept in an observable or experimental
basis. Ask the student "how would you test this?" for any claim. Use the graph
tool to plot data the student provides. Do not state laws or formulae — ask
the student to recall or derive them.
```

### General (`backend/specializations/general/prompt.txt`)
```
You are a Socratic tutor for general questions. Identify the core concept the
student is trying to understand. Ask them what they already know before
offering any framing. Use only questions and analogies — never definitions or
explanations offered unprompted.
```

---

## UI Components

### Always present
- **ChatPane** — the primary conversation surface, markdown-rendered, streaming

### Contextual (rendered when relevant)
- **SubproblemPanel** — decomposition tree, collapsible, status indicators
- **ToolPane** — slides in from right when a tool result is available
  - GraphView (iframe / img from backend render)
  - AlgebraSteps (step-by-step sympy output)
  - CodeOutput (terminal-style)
- **HintBadge** — subtle indicator on each subproblem node showing hint count
- **ConfidenceWidget** — 1–5 star selector, shown after each subproblem closes
- **CalibrationCheck** — 1–5 prediction asked *before* the student attempts a step (vs. ConfidenceWidget which fires after)
- **ReflectionPrompt** — inline card asking a metacognitive question; the response goes back as `directive_response` and is evaluated by the agent
- **CritiqueArtifactPanel** — shown in critique mode; renders the artifact under review
- **CritiqueFindingsList** — running list of issues the student has named, with `verified` state from coach probing
- **ThinkingTraceDrawer** — slides up at session end, shows narrative reflection

---

## Reflection & Calibration Subsystem

Two threads run alongside both loops. They are the product's most direct answer to the brief's "handle uncertainty" and "reflect on mistakes" targets.

### Periodic Reflection Prompts

The agent emits a `ReflectionPrompt` directive at four trigger points:

1. **Mid-session, periodic** — after every 2 closed subproblems (solving) or every 2 verified findings (critique). One question, calibrated to what just happened. Examples: *"What was different about how you approached sp-2 vs. sp-1?"* / *"You almost dropped that finding before catching it again — what made you take a second look?"*
2. **Self-correction follow-up** — when `control.self_correction_noted = true`, the *next* turn asks: *"What made you change your mind?"* Cheap, high-value moment.
3. **Escape hatch reflection** — the existing one-sentence gate before the answer is shown. Phase 3e of solving.
4. **Wrap-up reflection** — the synthesis question that produces `final_understanding` / `final_critique`.

Every reflection response is stored in `session.reflection_prompts` with the original question.

### Reflection Quality Evaluation

A reflection that says "I dunno, it just clicked" is less useful than one that says "I realized I was using the formula for X but the problem actually needed Y." The agent does a lightweight self-evaluation: on the turn *after* a reflection response, the agent sets `reflection_prompts[-1].quality` to `shallow | decent | deep` based on the response's content. If `shallow`, the agent follows up with one more probing question. **Maximum one follow-up per reflection** — no badgering.

This evaluation happens inside the same JSON output (`control.last_reflection_quality`), not as a separate LLM call.

### Calibration (Predict-then-Check)

Before the student attempts a subproblem (solving) or commits to a finding (critique), the agent may emit a `CalibrationCheck` directive: *"Before you try — how confident are you that you'll get this right? 1 to 5."* The student's answer is stored as a `calibration_point.predicted_confidence`. After the attempt resolves, the agent records the `outcome` (correct / wrong / partial) on the same point.

At wrap-up, the calibration trace becomes part of the thinking trace narrative:
- *"You predicted 4/5 confidence on three steps. You got two of them. Your gut is slightly ahead of your accuracy — worth noticing."*
- *"On the one you predicted 2/5, you actually nailed it. You knew more than you thought you did."*

Calibration is a v1 must-have, not a stretch goal: it's the only feature that directly trains uncertainty handling, which the brief calls out as a core target behaviour. The agent emits CalibrationCheck on at least one subproblem per session.

### Why these are in their own subsystem and not inside each loop

Solving and Critique both produce reflection prompts and calibration points. Keeping the subsystem orthogonal to mode means we can tune reflection frequency and evaluation strictness in one place rather than two prompts. The Socratic base prompt owns the contract; per-mode prompts only describe when to trigger, not how.

---

## Thinking Trace (formerly "session metrics")

> **Why this name matters**: This is not a performance score. It is a record of
> *how* the student thought — what they tried, where they got stuck, when they
> changed their mind. Framing it as a "trace" signals that the process is the
> point, not the answer.

Tracked automatically throughout the session. Shown as a reflection surface at wrap-up, never as a grade or score.

```json
{
  "mode": "solving | critique",
  "total_turns": 24,
  "phase_breakdown": { "clarification": 3, "decomposition": 5, "solving": 14, "wrap_up": 2 },
  "subproblems": [
    {
      "id": "sp-1",
      "description": "student's own words",
      "hints_used": 2,
      "direct_answer_requested": false,
      "escape_hatch_reflection": null,
      "confidence_score": 4
    }
  ],
  "critique_findings": [
    { "id": "f-1", "claim": "...", "kind": "factual_error", "verified": true, "was_self_corrected": false }
  ],
  "calibration_summary": {
    "points": [{ "predicted": 4, "outcome": "correct" }, { "predicted": 2, "outcome": "correct" }],
    "label": "well_calibrated | overconfident | underconfident | mixed",
    "evidence": "AI-generated 1-sentence summary of the pattern"
  },
  "reflection_summary": {
    "deep_reflections": 2,
    "decent_reflections": 1,
    "shallow_reflections": 0,
    "highlights": ["one or two of the deepest reflection quotes"]
  },
  "direct_answers_requested": 0,
  "self_corrections": 2,
  "initial_understanding": "I thought it was just about finding the roots",
  "final_understanding": "It's actually about the structure of the solution space",
  "understanding_delta_label": "significant | moderate | small",
  "understanding_delta_evidence": "AI-generated 1-sentence comparison of initial vs final",
  "initial_critique": null,
  "final_critique": null,
  "critique_delta_label": null,
  "critique_delta_evidence": null
}
```

`critique_findings`, `initial_critique`, `final_critique`, `critique_delta_*` are populated in critique mode. `subproblems`, `initial_understanding`, `final_understanding`, `understanding_delta_*` in solving mode. The other fields apply to both.

**Displayed to student as a narrative reflection, not a dashboard.** Solving mode:
- *"You broke the problem into N parts yourself and solved them in X turns."*
- *"You used hints on 2 of the 3 subproblems — on the third you got it without any."*
- *"At the start you said: '[initial_understanding]'. By the end you could explain: '[final_understanding]'. That shift is the learning."*
- *"You corrected your own thinking twice — noticing your own mistakes is a skill."*
- *"You predicted 4/5 confidence on three steps and got two — your gut is slightly ahead of your accuracy."*
- If escape hatch was used: *"On one step you asked for the answer directly. You wrote: '[escape_hatch_reflection]'. That moment of knowing you were stuck is worth remembering."*

Critique mode:
- *"You found N issues in this artifact. You retracted M of them after looking closer — that's calibration, not failure."*
- *"At first you said: '[initial_critique]'. After working through it: '[final_critique]'."*
- *"You missed [missed_issue]. Worth knowing — but you also caught [hardest_caught_issue], which most people gloss over."*

The understanding delta (solving) or critique delta (critique) is the most important output of the whole session. It is visible proof of thinking, not just task completion. This is the feature to demo in the pitch.

---

## API Endpoints

```
POST /session/new
  body: {
    username: string,                          // required
    mode: "solving",                           // v1 only accepts "solving"; "critique" lands in v1.1
    query: string,                             // required: the student's problem
  }
  returns: { session_id, mode, domain, opening_message }
  note: classifier runs internally via LLM_MODEL_CLASSIFIER. Anonymous sessions are not
        supported. In v1.1 the body grows an `artifact` field and mode accepts "critique".

POST /chat                                      [SSE]
  body: { session_id,
          message?: string,
          directive_response?: { component, value },
          tool_result?: { name, result, display_data, error? } }
  events:
    event: token             data: { delta: "..." }     // streamed chunks of reply
    event: state             data: { control: { ... } } // emitted once at end; validated control object
    event: frontend_tool     data: { name, args }       // present when control.tool_call resolves to a frontend tool
    event: error             data: { code, message }    // if the agent's output failed validation; client retries
  note: exactly one of message / directive_response / tool_result must be present.
        tool_result is sent when the frontend has executed a tool (execution: "frontend")
        and is feeding the result back. See "Generic tool dispatch" for the flow.
        See structured-output schemas in socratic_base.txt / critic_base.txt for control shape.

POST /tools/{tool_name}
  body: { session_id, ...tool-specific args }
  returns: { result, ui_component, display_data }
  note: tool_name must be registered in the active domain's manifest.json. Backend invokes
        these on the agent's behalf when control.tool_call is set; the result is replayed
        into the next turn's context. The frontend does not call this endpoint directly in v1.

GET /session/{session_id}/thinking-trace
  returns: { ...thinking trace object }
  note: shape varies by mode; see "Thinking Trace" section

POST /persona/create
  body: { username: string }
  returns: { status: "exists" | "pending", session_id?, persona? }
  note: on "pending", a short onboarding session_id is created; the frontend continues via
        /chat against the "persona" domain. On "exists", returns the stored persona.

POST /persona/reset
  body: { username: string }
  returns: { status: "reset" }

GET /specializations
  returns: [ { domain, display_name, tools: [], ui_components: [] } ]
  note: auto-generated from plugin registry. The frontend uses ui_components to validate
        that every component name has a matching entry in registry.ts at boot; missing
        names log a warning but do not block.
```

---

## LLM Prompt Construction (per turn)

```python
from app.prompts.variants import load_combined

def build_prompt(session: Session, user_message: str) -> list[dict]:
    # load_combined merges base + domain prompt; honours PROMPT_VARIANT_* env vars
    domain_prompt = load_combined(
        session.domain,
        base_variant=_VARIANT_BASE,
        domain_variant=_VARIANT_DOMAIN_MAP.get(session.domain),
    )
    persona_ctx = session.persona.to_context_str() if session.persona else ""
    return [
        {"role": "system", "content": domain_prompt},
        {"role": "system", "content": f"Student profile:\n{persona_ctx}"},
        {"role": "system", "content": f"Session state:\n{session.to_context_str()}"},
        *session.message_history,
        {"role": "user", "content": user_message}
    ]
```

`load_combined(domain)` concatenates `socratic_base.txt` + `specializations/<domain>/prompt.txt`
separated by `"\n\n"`. Variant keys (`base:v1`, `math:v2`, …) are resolved in
`backend/app/prompts/variants.py`. `_VARIANT_BASE` and `_VARIANT_DOMAIN_MAP` are
read once at `chat.py` module load from `PROMPT_VARIANT_BASE` / `PROMPT_VARIANT_DOMAIN`.

`session.to_context_str()` returns a compact JSON of current phase, active subproblem, hint count, and student's stated initial understanding.

The model to call is read from the `LLM_MODEL_TUTOR` / `LLM_MODEL_CLASSIFIER` environment variables and passed to OpenRouter. No model name is hardcoded anywhere in the application.

---

## Phase Transition Rules

```
clarification  →  decomposition   when: initial_understanding is captured
decomposition  →  solving         when: student confirms subproblem list
solving        →  solving         when: subproblem closes, next activates
solving        →  wrap_up         when: all subproblems are status=solved
```

Phase transitions are detected by the LLM (via a structured output call) or triggered explicitly by the student ("I think I've broken it down enough").

---

## Key Constraints (must be enforced in all system prompts)

1. **Never give the full solution.** Not even partially, unless the escape hatch is triggered.
2. **One question at a time.** Never ask two questions in the same message.
3. **Never enumerate subproblems.** Always ask the student to find them.
4. **Validate understanding before moving on.** Confidence check after each subproblem.
5. **Tools produce data, not answers.** Always ask the student to interpret tool output.
6. **Escape hatch is per-subproblem.** Giving away one step doesn't unlock the rest.

---

## Deployment

The product runs on the team's **AWS EC2 instance** (instance details in team channel, not in this repo).

### Topology

- One EC2 host runs both backend (FastAPI on port 8000) and frontend (static build served by nginx on port 80/443).
- Nginx is the public-facing entry: serves frontend static files, reverse-proxies `/api/*` to the FastAPI on 127.0.0.1:8000 (so SSE works without CORS gymnastics).
- HTTPS via Let's Encrypt (`certbot --nginx`). Re-uses the EC2 instance's public DNS or a team-provided subdomain.
- No load balancer, no autoscaling — this is a demo box.

### Process management

- Backend: `systemd` unit running `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`. Single worker because session state is in-memory; sticky sessions on multiple workers would need shared storage (out of scope for v1).
- Frontend: built into `frontend/dist/` at deploy time, served as static files. No node process in production.
- Logs to journald; `journalctl -u aporeka` reads them.

### Env vars

- Backend: `LLM_MODEL_TUTOR`, `LLM_MODEL_CLASSIFIER`, `LLM_MODEL_ARTIFACT`, `OPENROUTER_API_KEY`, `PERSONA_DIR` (defaults to `backend/personas/`), `ALLOWED_ORIGINS` (CSV, defaults to the public hostname).
- Frontend: built with `VITE_API_URL=/api` and `VITE_USE_MOCK=false`. The frontend never talks directly to OpenRouter.

### Secrets

- `OPENROUTER_API_KEY` lives in `/etc/aporeka.env` (`chmod 600`, owned by the service user). Read by the systemd unit via `EnvironmentFile=`. Never in the repo, never in a Docker image.

### Deploy scripts

All deploy artifacts live under `deploy/`. Hostname and host-specific paths are parameterized via a single config (`deploy/deploy.env`, gitignored), so the same scripts work on any host without code edits.

Files:
- `deploy/deploy.env.example` — committed template; deployer copies to `deploy.env` on the box and edits `APP_HOSTNAME` + `ADMIN_EMAIL`.
- `deploy/nginx.conf.template` — server block, `${APP_HOSTNAME}` substituted via `envsubst`. **SSE-ready directives pre-baked** (`proxy_buffering off`, `proxy_http_version 1.1`, long timeouts) so the future streaming work needs no nginx changes.
- `deploy/aporeka.service` — systemd unit template, `${APP_USER}` and `${APP_DIR}` substituted. Single worker (mandatory; in-memory sessions).
- `deploy/aporeka.env.template` — backend env template; rendered to `/etc/aporeka.env` with `chmod 600`.
- `deploy/bootstrap.sh` — one-time, root, idempotent. Installs apt deps (incl. Node 20 via NodeSource), renders templates, installs narrow sudoers entry for the deploy user, prints the exact certbot command to run.
- `deploy/deploy.sh` — every-deploy, run as `APP_USER`. `git pull` → backend `pip install` → frontend `npm ci && npm run build` → `rsync` to `/var/www/aporeka/` → restart backend → reload nginx → smoke test `/health` + `/specializations`.
- `frontend/.env.production` — `VITE_API_URL=/api`, `VITE_USE_MOCK=false`. Auto-loaded by `npm run build`.

First deploy (one-time):

```
ssh user@$APP_HOSTNAME
# clone repo to $APP_DIR (default /opt/aporeka/app), then:
cp deploy/deploy.env.example deploy/deploy.env  # edit APP_HOSTNAME + ADMIN_EMAIL
sudo bash deploy/bootstrap.sh
sudo nano /etc/aporeka.env               # replace replace-me with the real OPENROUTER_API_KEY
bash deploy/deploy.sh                            # app live on http://$APP_HOSTNAME
sudo certbot --nginx -d $APP_HOSTNAME --non-interactive --agree-tos -m $ADMIN_EMAIL
sudo systemctl enable aporeka             # survive reboots
```

Every subsequent deploy:

```
ssh user@$APP_HOSTNAME && cd $APP_DIR && bash deploy/deploy.sh
```

Sub-minute for code-only changes; ~2 min when deps change. CI/CD is out of scope for v1.

### Persona files in production

`backend/personas/*.json` is the only on-disk state. It survives restarts because it's a regular directory, not a tmpfs. Back up periodically by snapshotting the directory (a daily `tar.gz` to `~/persona-backups/` via cron is fine for v1). If the host is rebuilt, persona files must be preserved out-of-band — they are the only thing in this system that can't be regenerated.

---

## What to Build First (MVP cut + stretch)

The v1 MVP is the minimum that demonstrates the brief's "show and do, don't tell" thesis across all three core domains in Solving Mode. Critique Mode (the "judge AI outputs" axis) is designed and prompt-drafted but lands in v1.1, after v1 is stable in production.

### MVP (must ship before demo)

**Infrastructure**

1. ✅ **Plugin registry** — folder-scanning loader, manifest parser, tool dispatcher routing to backend tools or to the frontend bridge based on `execution`
2. ✅ **Socratic base prompt** — `backend/app/prompts/socratic_base.txt`, shared across all domains
3. ✅ **Core chat loop** — FastAPI `/chat` + OpenRouter relay + session state in memory + JSON schema validation of agent output (non-streaming; SSE is Priority 3)
4. ✅ **Domain detection** — classifier call in `/session/new` via `LLM_MODEL_CLASSIFIER`
5. ⬜ **Frontend tool bridge** — SSE `frontend_tool` event, `tool_result` POST body, handler registry at `frontend/src/specializations/<domain>/handlers/` (backend side wired; frontend dispatch not yet exercised because math tools are stubs)

**Solving mode**

6. ✅ **Solving phase state machine** — clarification → decomposition → solving → wrap-up; agent emits transitions, backend clamps illegal ones

**Domains** (all three required for v1)

7. ✅ **Math (school-level)** — prompt and manifest wired; algebra tool (sympy + implicit multiplication) and graph tool (matplotlib PNG + implicit multiplication) both implemented
8. ⬜ **Programming (intro Python)** — prompt and manifest wired; Pyodide runner and PseudocodePad not yet exercised
9. ⬜ **Essay (paragraph-level)** — prompt wired; OutlineTree component is a stub

**Cross-cutting product surface**

10. ✅ **Persona onboarding (short)** — `/persona/create` returns `exists`/`pending`; 2-turn onboarding via `"persona"` domain works; passive `persona_updates` field wired in session
11. ✅ **SubproblemPanel UI** — live decomposition tree, status badges, hint count
12. ✅ **Hint ladder + escape hatch** — tracked in session state; escape_hatch_triggered and escape_hatch_reflection fields in AgentControl
13. ✅ **Thinking trace + ThinkingTraceDrawer** — narrative reflection at wrap-up with understanding delta
14. ✅ **Reflection prompts with quality evaluation** — ReflectionPrompt component renders inline; backend auto-injects from `control.reflection_prompt`; quality evaluation fields wired in session schema
15. ✅ **Calibration (predict-then-check)** — CalibrationCheck component renders inline; backend auto-injects from `control.calibration_check`; phase guard prevents premature wrap_up; directive_response records predicted confidence
16. ✅ **Specialization UI registry + ToolPane** — registry.ts, ToolPane, inline/side_panel/modal directive placement all wired

**Ship**

17. 🟡 **Deploy to EC2** — deploy artifacts shipped under `deploy/` (bootstrap.sh, deploy.sh, nginx/systemd/env templates parameterized via `deploy/deploy.env`). First deploy on a real EC2 box still pending.

### Priority 2 — Math tools (DONE)

Both math tools are implemented:

- `backend/specializations/math/tools/algebra.py` — sympy `parse_expr` with `implicit_multiplication_application`; outputs `sympy.latex()` per step.
- `backend/specializations/math/tools/graph.py` — matplotlib Agg backend, plots over x_range, clips asymptotes, returns `data:image/png;base64` string. Also uses `implicit_multiplication_application` so `2x`, `3sin(x)` etc. work.

Both require the venv (`matplotlib`, `numpy`, `sympy` installed via `.venv/bin/pip install -e ".[dev,math]"`).

### Priority 3 — SSE streaming

`backend/app/llm.py` — implement `stream_tutor()`:
- Call OpenRouter with `stream=True`
- Yield `("token", delta)` tuples for content chunks
- Accumulate full response, parse JSON, yield `("state", control_obj)` at end
- On parse failure: retry once in non-streaming mode

Frontend `ChatPane` needs to consume `token` events to show streaming text and the `state` event to update session state.

### Priority 4 — Seeded dialogue tests

The probe suite (`tests/probes.py`) covers live-LLM regression gated behind `--run-slow`.
What is still missing is a **fast, deterministic gate**: seeded dialogues with canned LLM
replies injected via `fake_openrouter`, asserting the Socratic constraints hold turn-by-turn.

Add at least 3 seeded dialogues to `tests/test_socratic_constraints.py`:
- Each dialogue is a list of `(user_message, canned_llm_reply)` pairs
- Run assertions after each turn: `no_solution_leak`, `one_question`, `no_enumeration`
- Cover: math (algebra), programming (pseudocode ask), essay (no drafted paragraph)

Assertion helpers are already in the file. Use the `fake_openrouter` fixture from `conftest.py`.

### v1.1 (first post-MVP release)

18. **Critique Mode** — wire `critic_base.txt`, add artifact import + generated artifact paths (via `LLM_MODEL_ARTIFACT`), add the critique phase machine (clarification → critique → synthesis → wrap_up), build CritiqueArtifactPanel and CritiqueFindingsList, surface the second entry path on the landing screen. Design is in "The Critique Loop" above and `critic_base.txt`.

### v1.2+ (further additions, no fixed order)

19. **Seeded-flaw artifacts** — Critique mode's generated artifacts get a secondary editing pass that inserts a subtle error, raising critique difficulty
20. **Science specialization** — graph + data table tools, calibrated for school physics/biology
21. **General specialization** — fallback for queries that don't classify into math/programming/essay/science

### Stop-the-line items

The following are blockers that must hold throughout MVP development, not features to add:

- **Agent Socratic discipline.** Every model output must be validated against the rules (never give the answer, one question at a time, etc.). Build a regression harness for this in `backend/tests/test_socratic_constraints.py` early — seeded dialogues + assertions on forbidden patterns. If the model drifts on a swap, this catches it. v1 harness covers `socratic_base.txt` and the three v1 domain prompts; v1.1 expansion adds `critic_base.txt` coverage.
- **Pyodide load weight.** First load is ~10 MB. Lazy-load only when the programming domain is active; show a one-time "loading Python..." indicator. If load fails, the code_runner gracefully degrades — the agent falls back to "let's trace through this by hand" mode (no tool call). Never block the chat on Pyodide.
- **Three-domain prompt drift.** Each v1 domain prompt must pass the Socratic regression harness. Plan one full review pass per domain prompt before deploy.

---

## Out of Scope (v1)

- User login with passwords / auth tokens
- Firebase / cloud storage (personas are local JSON files on the EC2 disk)
- Cross-session learning (persona accumulates inferred fields, but agent does not adapt strategy across sessions)
- Multi-user concurrency stress (single worker, in-memory sessions — fine for demo, not for class rollout)
- Persona editing UI
- Teacher / parent dashboards
- Mobile-optimised layout (responsive enough not to break, but desktop-first)

These are documented for v2 but should not influence v1 architecture decisions. Keep session state in-memory and stateless across restarts, except for persona files.
