# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Deeper references** (load when the task needs them):
- Product design, solving loop, plugin system, session schema → [docs/DESIGN.md](docs/DESIGN.md)
- API endpoint reference → [docs/API.md](docs/API.md)
- Deployment guide → [docs/DEPLOY.md](docs/DEPLOY.md)
- Engineering issues and action plan → [ISSUES.md](ISSUES.md)
- Development roadmap → [PLAN.md](PLAN.md)
- Prompt-only issues → [PROMPT_ISSUES.md](PROMPT_ISSUES.md)

---

## Current State

**The core loop works end-to-end.** Phase machine (clarification → decomposition → solving → wrap_up), all FastAPI routes, domain detection, math tools (algebra + graph), expanded domain prompts (programming, essay, science), persona onboarding (two-step, confirm-new), thinking trace with understanding delta, CalibrationCheck/ReflectionPrompt widgets, JSONL logging, split prompt architecture, 17 probes, 135 fast tests.

### What is real and working

- **Backend** — all FastAPI routes are real: `/session/new`, `/chat`, `/persona/create`, `/persona/reset`, `/session/{id}/thinking-trace`, `/specializations`, `/tools/{tool_name}`. Plugin registry loads all specializations at startup.
- **Frontend** — all views/components implemented: `OnboardingView`, `SessionView`, `WrapUpView`, `ChatPane`, `SubproblemPanel`, `ToolPane`, `ThinkingTraceDrawer` (with `TraceHero` + `TraceReflections`), `CalibrationCheck`, `ReflectionPrompt`. Error boundary in `App.tsx`.
- **Mock mode** — `mock.ts` runs a scripted 7-turn conversation without API calls. Toggle via `VITE_USE_MOCK=true`.
- **Math tools** — `algebra.py` (sympy, implicit multiplication) and `graph.py` (matplotlib Agg, base64 PNG, asymptote clipping).
- **LaTeX** — KaTeX renders throughout via `MathText.tsx` (react-markdown + remark-math + rehype-katex).
- **Calibration + Reflection** — backend auto-injects `CalibrationCheck` and `ReflectionPrompt` directives from `signal` fields. XOR enforcement: `parsed.reply` is set to `None` when either directive is emitted, so the student never sees chat text alongside a directive card simultaneously.
- **Wrap-up dialogue** — multi-turn wrap-up works end-to-end. `wrap_up_complete: bool` on `ChatResponse` gates the `WrapUpView` transition (set when `last_reflection_quality` arrives against the wrap-up reflection). Frontend must NOT transition on `phase === "wrap_up"` alone.
- **Initial-understanding capture** — `session.initial_understanding` is populated deterministically at the clarification → next-phase transition via `_maybe_capture_initial_understanding`. No agent signal required.
- **Final-understanding** — `_maybe_run_wrap_up_summarizer` fires once at the first wrap_up turn and stores `final_understanding` + delta on session.
- **Summariser tone** — second-person ("You came to see…"), no graded language ("fragmented", "incomplete", "partial", "shallow"). Regression-tested in `test_llm_client.py`.
- **JSONL logging** — every LLM call lands in `backend/logs/llm.jsonl`; `/chat` turns also go to `chat.jsonl`.
- **Probe suite** — 17 probes in `backend/tests/probes.py`; run via `tests/run_probes.py`.
- **Split prompt architecture** — `backend/app/prompts/v1/` holds 8 files assembled per-turn by `load_base_prompt()` in `variants.py`.

### What is still a stub

- **SSE streaming** — `stream_tutor()` in `llm.py` raises `NotImplementedError`. All chat responses are currently non-streaming (full JSON on completion). See ISSUES.md #6.
- **Seeded dialogue tests** — `test_socratic_constraints.py` has assertion helpers but no deterministic seeded dialogue cases. See PLAN.md 1c.
- **EC2 deploy** — nginx + systemd setup documented in `docs/DEPLOY.md` but not yet executed. See ISSUES.md #2.
- **Critique Mode** — designed, prompt-drafted (`critic_base.txt`), deferred to v1.1. See ISSUES.md #3.
- **Calibration/reflection signals dormant in real sessions** — the UI is wired; the prompt needs tuning so the agent reliably emits `emit_calibration_check` / `emit_reflection`. See PLAN.md.

### Next milestones (in order)

1. Fix calibration/reflection emission (tune prompts or move to deterministic backend capture)
2. Implement SSE streaming (`stream_tutor()` + frontend ChatPane consumer)
3. Add seeded dialogue tests to `test_socratic_constraints.py`
4. Deploy to EC2

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
python -m tests.run_probes                              # all 17 probes
python -m tests.run_probes --probe json_schema_compliance
python -m tests.run_probes --model google/gemini-2.5-flash
python -m tests.run_probes --base-variant base:v2 --domain-variant math:v2
```

Results are appended to `backend/logs/probe_runs.jsonl`. Bold yellow `[MANUAL]` lines require human judgement — never counted in pass/fail.

### Socratic constraints test

```bash
cd backend
.venv/bin/pytest tests/test_socratic_constraints.py -v         # fast canned-reply tests
.venv/bin/pytest tests/test_socratic_constraints.py -v --run-slow  # include live-LLM slow tests
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

`probes/` holds scripted end-to-end sessions for human testers. Use when testing a new prompt or model — not automated.

| File | Domain | What it tests |
|---|---|---|
| `probe_01_fence.md` | Math | Fence optimisation — 5 subproblems, algebra + graph, escape hatch likely |
| `probe_02_bouncing_ball.md` | Math | Geometric series — graph convergence, sympy verification |
| `probe_03_essay.md` | Essay | Disengaged student — claim narrowing, counter-argument, no paragraph written |
| `random/test_scenario_fizzbuzz.md` | Programming | FizzBuzz — pseudocode first, then translation |
| `random/test_scenario_tickets.md` | Math | Word problem → system of equations |

### Prompt issues log

`PROMPT_ISSUES.md` tracks known prompt-level problems. Two open items: P11.1 (math tool before answer), P11.2 (essay counter-argument assertion too narrow). Check before editing prompt files.

### Temperature

| Var | Default | Why |
|---|---|---|
| `TUTOR_TEMPERATURE` | `0.7` | Natural variation in Socratic phrasing |
| `CLASSIFIER_TEMPERATURE` | `0.0` | Domain detection must be deterministic |
| `PROBE_TEMPERATURE` | `0.3` | Reproducible probe runs with minor phrasing variation |

### Prompt variants

Variant selection is **static per server process** — restart to switch. See `backend/app/prompts/variants.py`. Old keys stay registered so historical probe runs remain reproducible.

### LLM call logs

Every call is written to `backend/logs/llm.jsonl`. Set `LOG_LLM_CALLS=false` to suppress. `chat_turn` events are mirrored into both `llm.jsonl` and `chat.jsonl`.

### Log viewer

```bash
cd backend && .venv/bin/python scripts/view_logs.py logs/llm.jsonl
# custom host/port: --host 0.0.0.0 --port 5001
```

Open `http://127.0.0.1:5000`. Filter by session or event type, inspect thinking/reply/control/signal, export entries.

### Frontend (`frontend/`)

```bash
npm install
npm run dev          # port 5173
npm run typecheck    # type check (no ESLint yet)
npm run build
```

Required env vars (see `frontend/.env.example`):
- `VITE_API_URL` — backend URL (default `http://localhost:8000`)
- `VITE_USE_MOCK` — `true` to use the in-browser mock, `false` to hit the backend

---

## Implementation Notes

Critical findings from the initial implementation pass. Read this before touching the LLM or backend layer.

### Running the servers

**Do not use `--reload` with uvicorn.** WatchFiles hot-reload silently serves stale `.pyc` files. Always do a clean restart:

```bash
pkill -f "uvicorn app.main" 2>/dev/null; sleep 1
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Always restart the backend after changing any `.py` file or `.txt` prompt.** Temperature and variant env vars are read once at module load.

Frontend Vite hot-reload works fine.

### Python version and venv

The venv is at `backend/.venv/` (Python 3.12). Always use it:

```
backend/.venv/bin/python   ← server and tests
backend/.venv/bin/pytest   ← must use this, not the system pytest
```

### Environment configuration (`.env`)

Current working configuration:

```
OPENROUTER_API_KEY=<key>
LLM_MODEL_TUTOR=google/gemini-2.5-flash
LLM_MODEL_CLASSIFIER=qwen/qwen3.6-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
PERSONA_DIR=./personas
ALLOWED_ORIGINS=http://localhost:5173
LLM_MAX_TOKENS=2048
```

`LLM_MAX_TOKENS=512` was too low (models need ~300 for reply + ~200 for control JSON). `load_dotenv()` is called in `main.py` — `.env` is loaded automatically.

### The `_strip_fences` fix (critical — do not revert)

`backend/app/llm.py` applies `_strip_fences()` to every model response before `json.loads()`. This is essential: `google/gemini-2.5-flash` ignores `json_object` format and returns markdown prose followed by a ` ```json ` block. Without this, `json.loads()` fails on every response.

`_strip_fences` uses `re.findall` to collect **all** ` ```json ` blocks and returns the **last** one — because earlier blocks may be math expressions, not the control JSON.

### Phase transition clamping

Illegal phase transitions (e.g. model jumping `clarification → wrap_up`) are clamped to the current phase in `_validate_phase()` in `chat.py`. A warning is logged. `_apply_agent_response` does **not** touch `session.phase` — the caller owns transitions (fixes the clamping overwrite bug).

### Dev persona shortcut

`backend/personas/testuser.json` is pre-created and committed. Username `testuser` skips the 2-turn LLM onboarding entirely.

### Error visibility

`frontend/api/client.ts` extracts the `detail` field from FastAPI error responses. `SessionView` displays it as `Error: <detail>` in the chat.

### LaTeX rendering (MathText component)

All math rendering goes through `frontend/src/components/MathText.tsx` (react-markdown + remark-math + rehype-katex). KaTeX CSS is bundled in `main.tsx`, not CDN. For display math (`$$`), the expression must be on its own paragraph with surrounding blank lines.

### Algebra tool — implicit multiplication

`backend/specializations/math/tools/algebra.py` uses `parse_expr` with `implicit_multiplication_application`, so `2x`, `2x+3=7`, `3(x+1)=15` all parse correctly. Do **not** revert to bare `sympify()`.

### Tool-call loop fix (critical — do not revert)

`_run_chat_turn` has three guards preventing infinite tool loops:

1. **Unconditional assistant message** — added before the tool result every iteration. Without it, the model re-issues the same call.
2. **Same-tool dedup** — if the model calls the same tool twice in a row after receiving its result, the loop breaks.
3. **`"role": "user"` for tool result** — Gemini follows user-role instructions more reliably than system-role.

### CalibrationCheck + ReflectionPrompt auto-injection

The backend auto-injects both widgets in `_build_chat_response`. The model emits only a trigger type; the backend owns the question text.

- `signal.emit_calibration_check: true` → injects a `CalibrationCheck` directive. Question is always backend-curated.
- `signal.emit_reflection: "trigger_type"` → backend selects from `REFLECTION_QUESTIONS[trigger_type]` (defined in `chat.py`). Question is chosen once in `_apply_agent_response`, stored via `session.pending_reflection_index`, reused in `_build_chat_response`.

**XOR rule**: `_finalize_turn` sets `parsed.reply = None` when either signal is present.
**Phase guard**: if `emit_calibration_check` is true and `control.phase == "wrap_up"` on the same turn, the phase transition is blocked.
**De-duplication**: if the agent already emitted a directive of the same component name, the backend does not add a second one.

### wrap_up_complete and the transition gate

`ChatResponse` carries `wrap_up_complete: bool`. Set to `True` in `_finalize_turn` when:
- `session.phase == "wrap_up"` AND `session.pending_reflection_index is None` after `_apply_agent_response` runs (covers: reflection quality evaluated → index cleared; wrap_up without reflection → index never set).
- `False` while a reflection is still pending.

The frontend (`SessionView.tsx`) must gate the `WrapUpView` transition on `res.wrap_up_complete === true`, NOT on `res.phase === "wrap_up"`. The manual "End session →" button remains as the fallback.

### Structured output schema (current — three top-level keys)

```json
{
  "thinking": "scratchpad — stripped before any processing",
  "reply": "message to student (null when a directive is emitted exclusively)",
  "control": {
    "phase":             "clarification | decomposition | solving | wrap_up | null",
    "active_subproblem": "sp-1 | null",
    "hint_level":        null,
    "tool_call":         { "name": "...", "args": {} } | null,
    "ui_directives":     []
  },
  "signal": {
    "subproblem_updates":      [ { "id", "description", "goal", "status" } ],
    "emit_reflection":         "periodic | self_correction | escape_hatch | wrap_up",
    "last_reflection_quality": "shallow | decent | deep",
    "emit_calibration_check":  true,
    "calibration_outcome":     "correct | wrong | partial",
    "persona_updates":         [ { "field", "operation", "value", "evidence", "inferred" } ],
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

`thinking` is popped before `AgentResponse.model_validate()`. `signal` is optional — absent on quiet turns. `hint_level: null` is a no-op. `subproblem_updates` live in `signal`, not `control`.

### `call_tutor` and `call_classifier` return type

Both return a **2-tuple** `(parsed_output, token_usage)`:

```python
raw_dict, usage = await llm.call_tutor(messages, session_id=session.session_id, temperature=_TUTOR_TEMP)
result, usage   = await llm.call_classifier(query, temperature=_CLASSIFIER_TEMP)
```

The `fake_openrouter` fixture patches `_post_chat` (not `call_tutor`), so its `Recorder` only needs to accept the `temperature` kwarg.

### One-question threshold (> 2, not > 1)

`assert_one_question_per_turn` fails when a reply contains **more than 2** `?` characters. This allows parenthetical clarifiers like `"What rule applies here (do you remember it?)"`. Consistent across `test_socratic_constraints.py` and `probes.py`.

### Prompt variant system

`VARIANTS` maps string keys to `Path` objects. `parse_domain_variants(env_value)` raises `ValueError` at startup on malformed entries (missing `:`). Old keys stay registered so historical probe runs remain reproducible.

### Initial-understanding capture

`session.initial_understanding` is **not** populated from any agent signal. Capture is deterministic via `_maybe_capture_initial_understanding(session, previous_phase)`, called from `_finalize_turn` and `/session/new` right after `_validate_phase`:

1. Returns early if `session.initial_understanding` is already set (idempotent).
2. Returns early if the session is still in clarification or never was.
3. Collects student's clarification-phase messages from `session.message_history`.
4. Awaits `llm.call_initial_understanding_summarizer(...)` → one-sentence second-person summary or `None` on failure.
5. Stores the result on the session.

This pattern (deterministic backend capture, no agent signal) is the model to follow for `emit_reflection` / `emit_calibration_check` if those are ever moved off the agent's hands.

### `fake_openrouter` test fixture stubs the initial summariser

`conftest.py` monkeypatches `llm.call_initial_understanding_summarizer` to a no-op (`return None`) by default. Reason: the clarification → next-phase capture would otherwise consume one extra queued LLM response on every test that drives a phase transition out of clarification.

Tests that exercise the real capture override this stub with their own `monkeypatch.setattr`.

---

## Decisions (locked in)

The six integration-shape decisions below were debated and confirmed. Changes require updating dependent sections in the same PR.

1. **Agent structured output** — single JSON object via OpenRouter structured outputs (JSON Schema mode). Shape: `{ "thinking", "reply", "control", "signal" }`. Fallback: JSON mode + Pydantic parsing with one retry on parse failure.
2. **Streaming** — Server-Sent Events on `/chat`. Two event types: `token` (chunks of `reply`) and `state` (validated `control` + `wrap_up_complete` at end). Non-streaming JSON is the fallback. (SSE not yet implemented — `stream_tutor()` raises `NotImplementedError`.)
3. **Agent decision authority** — agent owns all phase transitions, hint escalation, subproblem creation, tool calls. Backend is a validator: clamps illegal moves with a warning log.
4. **Domain detection** — runs inside `/session/new` via `LLM_MODEL_CLASSIFIER` (a cheap model, separate from `LLM_MODEL_TUTOR`). `query` is stored as the first user message; `opening_message` is the tutor's first reply, produced in the same call.
5. **Onboarding** — runs through `/chat` with reserved domain `"persona"` (a specialization at `backend/specializations/persona/`). Not user-selectable; excluded from `/specializations`.
6. **Username required** on `/session/new`. No anonymous sessions in v1.

---

## Repository Layout

```
bootcamp-metacognition-project/
├── backend/
│   ├── app/
│   │   ├── main.py             ← FastAPI entrypoint, route mounting
│   │   ├── chat.py             ← /chat, /session/new handlers; session state machine
│   │   ├── persona.py          ← /persona/create, /persona/reset handlers
│   │   ├── session.py          ← in-memory session store + Session model
│   │   ├── plugin_registry.py  ← folder-scanning loader, tool dispatcher
│   │   ├── llm.py              ← OpenRouter client; call_tutor, call_classifier, call_summarizer
│   │   └── prompts/v1/         ← 8 prompt files assembled per-turn
│   ├── specializations/        ← math/, programming/, essay/, science/, general/, persona/
│   ├── personas/               ← runtime persona JSON files (gitignored except .gitkeep)
│   ├── tests/
│   ├── scripts/view_logs.py    ← local Flask UI for llm.jsonl
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   ├── client.ts       ← fetch wrapper, base URL from VITE_API_URL
│   │   │   ├── types.ts        ← mirrors backend schemas (ChatResponse, ThinkingTrace, …)
│   │   │   └── mock.ts         ← in-browser mock; toggle via VITE_USE_MOCK
│   │   ├── components/         ← ChatPane, SubproblemPanel, ToolPane, ThinkingTraceDrawer, …
│   │   ├── specializations/    ← domain UI components + frontend tool handlers
│   │   │   └── registry.ts     ← maps "<domain>.<component>" → React component
│   │   └── views/              ← OnboardingView, SessionView, WrapUpView
│   └── package.json
│
├── docs/
│   ├── DESIGN.md               ← product design, solving loop, plugin system, session schema
│   ├── API.md                  ← API endpoint reference
│   └── DEPLOY.md               ← deployment guide
│
├── probes/                     ← human-run scripted test scenarios
├── reflections/                ← team journals (ignore for engineering tasks)
├── ISSUES.md                   ← engineering issues with root causes and action items
├── PLAN.md                     ← development roadmap by priority tier
├── PROMPT_ISSUES.md            ← prompt-only issues (no code changes needed)
└── CLAUDE.md
```

**Cross-cutting rules:**
- Frontend never imports from `backend/`. Shared shapes are mirrored by hand in `frontend/src/api/types.ts`.
- The frontend must work standalone with `VITE_USE_MOCK=true`.
- A **specialization is a pair**: `backend/specializations/<domain>/` AND `frontend/src/specializations/<domain>/`. Both halves must land together.
- API contract changes require updating both sides plus `docs/API.md` in the same PR.
