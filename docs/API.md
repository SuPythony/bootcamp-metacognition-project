# Aporeka — API Reference

All endpoints are on the FastAPI backend (default port 8000). The frontend never talks directly to OpenRouter; all LLM calls flow through the backend.

---

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
    event: state             data: { control: { ... }, wrap_up_complete?: bool }
    event: frontend_tool     data: { name, args }       // present when control.tool_call resolves to a frontend tool
    event: error             data: { code, message }    // if the agent's output failed validation; client retries
  note: exactly one of message / directive_response / tool_result must be present.
        tool_result is sent when the frontend has executed a tool (execution: "frontend")
        and is feeding the result back. See "Generic tool dispatch" in docs/DESIGN.md.
        wrap_up_complete=true signals the frontend to transition to WrapUpView; do NOT
        transition on phase="wrap_up" alone.

POST /tools/{tool_name}
  body: { session_id, ...tool-specific args }
  returns: { result, ui_component, display_data }
  note: tool_name must be registered in the active domain's manifest.json. Backend invokes
        these on the agent's behalf when control.tool_call is set; the result is replayed
        into the next turn's context. The frontend does not call this endpoint directly in v1.

GET /session/{session_id}/thinking-trace
  returns: { ...thinking trace object }
  note: shape varies by mode; see docs/DESIGN.md "Thinking Trace" section.
        Called once by WrapUpView after the session ends.

POST /persona/create
  body: { username: string, confirm?: bool }
  returns: { status: "exists" | "pending" | "confirm_new", session_id?, persona? }
  note: on "pending", a short onboarding session_id is created; the frontend continues via
        /chat against the "persona" domain. On "exists", returns the stored persona.
        On "confirm_new", the username is new but confirm was not set — prompt the user
        to confirm before actually creating the persona.

POST /persona/reset
  body: { username: string }
  returns: { status: "reset" }

GET /specializations
  returns: [ { domain, display_name, tools: [], ui_components: [] } ]
  note: auto-generated from plugin registry. The frontend uses ui_components to validate
        that every component name has a matching entry in registry.ts at boot; missing
        names log a warning but do not block. The "persona" domain is excluded
        (internal: true in its manifest.json).
```

---

## ChatResponse shape (state event payload)

```json
{
  "reply": "message to the student (null when a directive was emitted exclusively)",
  "phase": "clarification | decomposition | solving | wrap_up",
  "subproblems": [ { "id", "description", "goal", "status", "hints_given" } ],
  "active_subproblem": "sp-1 | null",
  "hint_level": null,
  "ui_directives": [
    {
      "component": "CalibrationCheck | ReflectionPrompt | RuleRecallPrompt | ...",
      "domain": "math | ...",
      "props": {},
      "placement": "inline | side_panel | modal",
      "lifetime": "until_dismissed | until_next_turn | persistent_in_subproblem"
    }
  ],
  "wrap_up_complete": false
}
```

`reply` is null (not absent) when the backend suppressed chat text in favour of a directive (XOR rule). `wrap_up_complete` is false during the multi-turn wrap-up dialogue; transitions to true once `last_reflection_quality` arrives against the wrap-up reflection, clearing `pending_reflection_index`.
