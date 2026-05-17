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
  result?: unknown;
  ui_component?: string;
  display_data?: Record<string, unknown>;
  args?: Record<string, unknown>;
  execution?: "backend" | "frontend";
}

export interface ChatResponse {
  // reply can be null on tool-only turns per the agent output schema
  reply: string | null;
  phase: Phase;
  subproblems: Subproblem[];
  tool_calls: ToolCall[];
  ui_directives: UIDirective[];
  onboarding_complete?: boolean;
  /** True when the wrap_up reflection cycle is complete and WrapUpView should load. */
  wrap_up_complete?: boolean;
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
  tool_result?: {
    name: string;
    result?: unknown;
    display_data?: unknown;
    error?: string | null;
  };
}

// Inferred persona field — wraps a value with provenance.
// Backend uses these objects for any field captured passively from chat
// (vs. answered explicitly during onboarding).
export interface PersonaField<T = string> {
  value: T;
  inferred: boolean;
  evidence?: string | null;
}

export interface Persona {
  username: string;
  created_at: string;
  // Flat strings — captured directly at onboarding.
  age_band?: string | null;
  school_level?: string | null;
  initial_intent?: string | null;
  // Inferred fields — present once the agent extracts them passively.
  education_detail?: PersonaField | null;
  confident_subjects?: PersonaField[];
  difficult_subjects?: PersonaField[];
  learning_style?: PersonaField | null;
  preferred_pace?: PersonaField | null;
  goals?: PersonaField | null;
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
  initial_understanding: string | null;
  final_understanding: string | null;
  understanding_delta_label: "significant" | "moderate" | "small" | null;
  understanding_delta_evidence: string | null;
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
  calibration_summary?: {
    points: Array<{ predicted: number; outcome: "correct" | "wrong" | "partial" }>;
    label: "well_calibrated" | "overconfident" | "underconfident" | "mixed" | null;
    evidence: string | null;
  };
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
