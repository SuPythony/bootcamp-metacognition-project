// In-browser mock. Must satisfy the same contract as the real backend so the
// frontend can develop standalone with VITE_USE_MOCK=true (CLAUDE.md, "Cross-cutting rules").
// Mock must also emit ui_directives so the component renderer is exercised in mock mode.

import type {
  ChatRequest,
  ChatResponse,
  PersonaCreateResponse,
  SessionNewRequest,
  SessionNewResponse,
  SpecializationManifestEntry,
  ThinkingTrace,
} from "./types";

export async function sessionNew(
  _body: SessionNewRequest,
): Promise<SessionNewResponse> {
  return {
    session_id: "mock-session",
    domain: "math",
    opening_message:
      "Before we dig in — what's your current thinking on this? Even a rough intuition is fine.",
  };
}

export async function chat(_body: ChatRequest): Promise<ChatResponse> {
  return {
    reply: "What rule do you think applies here?",
    phase: "solving",
    subproblems: [],
    tool_calls: [],
    ui_directives: [
      {
        component: "RuleRecallPrompt",
        domain: "math",
        props: {
          candidate_rules: ["distributive", "associative", "commutative"],
          context_expr: "3(x + 2)",
        },
        placement: "inline",
        lifetime: "until_next_turn",
      },
    ],
  };
}

export async function personaCreate(
  username: string,
): Promise<PersonaCreateResponse> {
  return { status: "pending", session_id: `mock-persona-${username}` };
}

export async function thinkingTrace(_sessionId: string): Promise<ThinkingTrace> {
  return {
    total_turns: 0,
    phase_breakdown: {
      clarification: 0,
      decomposition: 0,
      solving: 0,
      wrap_up: 0,
    },
    subproblems: [],
    direct_answers_requested: 0,
    self_corrections: 0,
    initial_understanding: "",
    final_understanding: "",
    understanding_delta_label: "small",
    understanding_delta_evidence: "",
  };
}

export async function specializations(): Promise<SpecializationManifestEntry[]> {
  return [
    {
      domain: "math",
      display_name: "Mathematics",
      tools: [],
      ui_components: [],
    },
  ];
}
