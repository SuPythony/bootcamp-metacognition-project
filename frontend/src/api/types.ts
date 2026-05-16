// Mirrors backend schemas. If these drift from CLAUDE.md, fix here.
// Follow-up: auto-generate from FastAPI's OpenAPI schema (CLAUDE.md, "Open follow-ups").

export type Domain =
  | "math"
  | "programming"
  | "essay"
  | "science"
  | "general"
  | "persona";

export type Phase = "clarification" | "decomposition" | "solving" | "wrap_up";

export interface Subproblem {
  id: string;
  description: string;
  goal: string;
  status: "pending" | "active" | "solved";
  hints_given: number;
  direct_answer_requested: boolean;
}

export interface UIDirective {
  component: string;
  domain: Domain;
  props: Record<string, unknown>;
  placement: "inline" | "side_panel" | "modal";
  lifetime:
    | "until_dismissed"
    | "until_next_turn"
    | "persistent_in_subproblem";
}

export interface ToolCall {
  name: string;
  ui_component?: string;
  display_data?: Record<string, unknown>;
  args?: Record<string, unknown>;
}

export interface ChatResponse {
  // reply can be null on tool-only turns per the agent output schema
  reply: string | null;
  phase: Phase;
  subproblems: Subproblem[];
  tool_calls: ToolCall[];
  ui_directives: UIDirective[];
  onboarding_complete?: boolean;
}

export interface SessionNewRequest {
  query: string;
  username: string;
  mode?: "solving";
}

export interface SessionNewResponse {
  session_id: string;
  domain: Domain;
  opening_message: string;
}

export interface ChatRequest {
  session_id: string;
  message?: string;
  directive_response?: { component: string; value: unknown };
}

export interface Persona {
  username: string;
  created_at: string;
  education_level:
    | "undergraduate"
    | "high_school"
    | "self_taught"
    | "professional"
    | "other";
  education_detail: string;
  confident_subjects: string[];
  difficult_subjects: string[];
  learning_style:
    | "examples_first"
    | "theory_first"
    | "trial_and_error"
    | "mixed";
  goals: string;
  preferred_pace: "slow" | "medium" | "fast";
  raw_responses: { question: string; answer: string }[];
}

export interface PersonaCreateResponse {
  status: "exists" | "pending" | "confirm_new";
  session_id?: string;
  persona?: Persona;
  opening_message?: string;
}

export interface ThinkingTrace {
  total_turns: number;
  phase_breakdown: Record<Phase, number>;
  subproblems: Array<{
    id: string;
    description: string;
    hints_used: number;
    direct_answer_requested: boolean;
    escape_hatch_reflection: string | null;
    confidence_score: number | null;
  }>;
  direct_answers_requested: number;
  self_corrections: number;
  initial_understanding: string;
  final_understanding: string;
  understanding_delta_label: "significant" | "moderate" | "small";
  understanding_delta_evidence: string;
  reflection_prompts?: Array<{
    trigger: string;
    question: string;
    response: string | null;
    quality: "shallow" | "decent" | "deep" | null;
  }>;
  calibration_points?: Array<{
    subproblem_id: string;
    predicted_confidence: number;
    outcome: "correct" | "wrong" | "partial" | null;
  }>;
}

export interface StreamCallbacks {
  onToken: (delta: string) => void;
  onState: (state: ChatResponse) => void;
  onError: (message: string) => void;
}

export interface SpecializationManifestEntry {
  domain: Domain;
  display_name: string;
  tools: Array<{
    name: string;
    description: string;
    endpoint: string;
    ui_component: string;
    input_schema: Record<string, unknown>;
  }>;
  ui_components: Array<{
    name: string;
    description: string;
    props_schema: Record<string, unknown>;
    trigger: "tool_result" | "agent_directive";
  }>;
}
