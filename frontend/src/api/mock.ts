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

// Cycle through a scripted conversation to exercise all UI surfaces.
let turnCount = 0;

const SCRIPTED_TURNS: ChatResponse[] = [
  // Turn 1 — user replied to opening question, move to decomposition
  {
    reply:
      "Good start. Now let's figure out the structure. What would you need to work out first before you can solve the whole thing?",
    phase: "decomposition",
    subproblems: [],
    tool_calls: [],
    ui_directives: [],
  },
  // Turn 2 — decomposition continues, subproblems appear
  {
    reply:
      "Good start. Now let's break this down. What would you need to figure out first before you can solve the whole thing?",
    phase: "decomposition",
    subproblems: [
      {
        id: "sp-1",
        description: "Isolate the variable term on one side",
        goal: "Get 2x alone",
        status: "active",
        hints_given: 0,
        direct_answer_requested: false,
      },
    ],
    tool_calls: [],
    ui_directives: [],
  },
  // Turn 3 — solving, RuleRecallPrompt inline
  {
    reply: "Nice. Before we simplify, which algebraic rule applies here?",
    phase: "solving",
    subproblems: [
      {
        id: "sp-1",
        description: "Isolate the variable term on one side",
        goal: "Get 2x alone",
        status: "active",
        hints_given: 0,
        direct_answer_requested: false,
      },
      {
        id: "sp-2",
        description: "Divide both sides by the coefficient",
        goal: "Find x",
        status: "pending",
        hints_given: 0,
        direct_answer_requested: false,
      },
    ],
    tool_calls: [],
    ui_directives: [
      {
        component: "RuleRecallPrompt",
        domain: "math",
        props: {
          candidate_rules: ["distributive", "inverse operations", "commutative"],
          context_expr: "2x + 3 = 7",
        },
        placement: "inline",
        lifetime: "until_next_turn",
      },
    ],
  },
  // Turn 4 — hint given, badge updates
  {
    reply:
      "Close — think about what operation undoes addition. What would you do to both sides?",
    phase: "solving",
    subproblems: [
      {
        id: "sp-1",
        description: "Isolate the variable term on one side",
        goal: "Get 2x alone",
        status: "active",
        hints_given: 1,
        direct_answer_requested: false,
      },
      {
        id: "sp-2",
        description: "Divide both sides by the coefficient",
        goal: "Find x",
        status: "pending",
        hints_given: 0,
        direct_answer_requested: false,
      },
    ],
    tool_calls: [],
    ui_directives: [],
  },
  // Turn 5 — sp-1 solved, sp-2 active, confidence modal
  {
    reply:
      "Exactly right — subtracting 3 from both sides gives 2x = 4. Now for the second part: how do you get x on its own?",
    phase: "solving",
    subproblems: [
      {
        id: "sp-1",
        description: "Isolate the variable term on one side",
        goal: "Get 2x alone",
        status: "solved",
        hints_given: 1,
        direct_answer_requested: false,
      },
      {
        id: "sp-2",
        description: "Divide both sides by the coefficient",
        goal: "Find x",
        status: "active",
        hints_given: 0,
        direct_answer_requested: false,
      },
    ],
    tool_calls: [],
    ui_directives: [],
  },
  // Turn 6 — wrap up
  {
    reply:
      "Perfect — x = 2. Can you now explain the full solution in your own words, start to finish?",
    phase: "wrap_up",
    subproblems: [
      {
        id: "sp-1",
        description: "Isolate the variable term on one side",
        goal: "Get 2x alone",
        status: "solved",
        hints_given: 1,
        direct_answer_requested: false,
      },
      {
        id: "sp-2",
        description: "Divide both sides by the coefficient",
        goal: "Find x",
        status: "solved",
        hints_given: 0,
        direct_answer_requested: false,
      },
    ],
    tool_calls: [],
    ui_directives: [],
  },
];

export async function sessionNew(
  _body: SessionNewRequest,
): Promise<SessionNewResponse> {
  turnCount = 0;
  return {
    session_id: "mock-session",
    domain: "math",
    opening_message:
      "Before we dig in — what's your current thinking on this? Even a rough intuition is fine.",
  };
}

export async function chat(_body: ChatRequest): Promise<ChatResponse> {
  const turn = SCRIPTED_TURNS[Math.min(turnCount, SCRIPTED_TURNS.length - 1)];
  turnCount++;
  return turn;
}

export async function personaCreate(
  username: string,
): Promise<PersonaCreateResponse> {
  return { status: "pending", session_id: `mock-persona-${username}` };
}

export async function thinkingTrace(_sessionId: string): Promise<ThinkingTrace> {
  return {
    total_turns: 6,
    phase_breakdown: {
      clarification: 1,
      decomposition: 1,
      solving: 3,
      wrap_up: 1,
    },
    subproblems: [
      {
        id: "sp-1",
        description: "Isolate the variable term on one side",
        hints_used: 1,
        direct_answer_requested: false,
        escape_hatch_reflection: null,
        confidence_score: 4,
      },
      {
        id: "sp-2",
        description: "Divide both sides by the coefficient",
        hints_used: 0,
        direct_answer_requested: false,
        escape_hatch_reflection: null,
        confidence_score: 5,
      },
    ],
    direct_answers_requested: 0,
    self_corrections: 1,
    initial_understanding: "I thought I needed to multiply both sides first",
    final_understanding:
      "I need to isolate x by applying inverse operations in reverse order of BIDMAS",
    understanding_delta_label: "significant",
    understanding_delta_evidence:
      "You went from thinking about multiplication first to correctly identifying inverse operations applied in the right sequence.",
  };
}

export async function specializations(): Promise<SpecializationManifestEntry[]> {
  return [
    {
      domain: "math",
      display_name: "Mathematics",
      tools: [],
      ui_components: [
        {
          name: "AlgebraSteps",
          description: "Step-by-step symbolic manipulation",
          props_schema: {},
          trigger: "tool_result",
        },
        {
          name: "RuleRecallPrompt",
          description: "Asks student to pick the rule that applies",
          props_schema: {},
          trigger: "agent_directive",
        },
      ],
    },
  ];
}
