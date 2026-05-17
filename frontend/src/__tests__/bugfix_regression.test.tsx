/**
 * Regression tests for the May-2026 bug-hunt sweep (frontend half).
 *
 * Each test name embeds the symptom of one fixed bug so failing tests read
 * as a punch list. Don't mute or weaken these without re-running the bug
 * hunt — they exist because the bug shipped silently once.
 */

import { describe, it, expect, vi } from "vitest";

// ---------------------------------------------------------------------------
// api/types.ts — ChatRequest must declare tool_result
// ---------------------------------------------------------------------------

describe("api/types", () => {
  it("ChatRequest accepts a tool_result field (Pyodide round-trip)", async () => {
    const types = await import("../api/types");
    // Compile-time check: the request shape must allow tool_result.
    // If this file fails to type-check, ChatRequest is missing the field.
    const req: import("../api/types").ChatRequest = {
      session_id: "s",
      tool_result: { name: "code_runner", result: 42 },
    };
    expect(req.tool_result?.name).toBe("code_runner");
    void types; // silence import
  });

  it("Persona uses inferred-field objects, not flat strings", async () => {
    // Compile-time check that PersonaField wraps inferred values.
    const p: import("../api/types").Persona = {
      username: "alex",
      created_at: "2026-05-17T00:00:00Z",
      age_band: "16-18",
      confident_subjects: [
        { value: "algebra", inferred: true, evidence: "solved sp-1 w/o hints" },
      ],
    };
    expect(p.confident_subjects?.[0]?.inferred).toBe(true);
    expect(p.confident_subjects?.[0]?.value).toBe("algebra");
  });

  it("ThinkingTrace.understanding_delta_label tolerates null (summariser failure)", async () => {
    const t: import("../api/types").ThinkingTrace = {
      total_turns: 1,
      phase_breakdown: {
        clarification: 1,
        decomposition: 0,
        solving: 0,
        wrap_up: 0,
      },
      subproblems: [],
      direct_answers_requested: 0,
      self_corrections: 0,
      initial_understanding: null,
      final_understanding: null,
      understanding_delta_label: null,
      understanding_delta_evidence: null,
    };
    expect(t.understanding_delta_label).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// specializations/registry — silent has(), dedup warnings on lookup()
// ---------------------------------------------------------------------------

describe("specializations registry warning dedup", () => {
  it("has() probe does not emit console.warn", async () => {
    const reg = await import("../specializations/registry");
    reg._resetLookupWarningsForTests();
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    reg.has("nope.NoSuchComponent");
    reg.has("nope.NoSuchComponent");
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("lookup() warns once per missing key, not on every probe", async () => {
    const reg = await import("../specializations/registry");
    reg._resetLookupWarningsForTests();
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    reg.lookup("nope.OncePerKey");
    reg.lookup("nope.OncePerKey");
    reg.lookup("nope.OncePerKey");
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// CalibrationPlot — off-by-one tolerance
// ---------------------------------------------------------------------------

describe("CalibrationPlot classify (off-by-one tolerance)", () => {
  it("predicted 4 + correct outcome (mapped 5) is calibrated, not under", async () => {
    // We can't import the inner `classify` directly (it's module-local), so
    // assert on the rendered summary text, which is built from classify().
    const { render } = await import("@testing-library/react");
    const { CalibrationPlot } = await import("../components/trace/CalibrationPlot");
    const trace: import("../api/types").ThinkingTrace = {
      total_turns: 0,
      phase_breakdown: { clarification: 0, decomposition: 0, solving: 0, wrap_up: 0 },
      subproblems: [],
      direct_answers_requested: 0,
      self_corrections: 0,
      initial_understanding: "",
      final_understanding: "",
      understanding_delta_label: "small",
      understanding_delta_evidence: "",
      calibration_points: [
        { subproblem_id: "sp-1", predicted_confidence: 4, outcome: "correct" },
        { subproblem_id: "sp-2", predicted_confidence: 5, outcome: "correct" },
      ],
    };
    const { container } = render(<CalibrationPlot trace={trace} />);
    const text = container.textContent?.toLowerCase() ?? "";
    // Both points should count as calibrated (predicted ≈ actual within 1).
    expect(text).toContain("calibration");
    expect(text).not.toContain("underconfident");
  });

  it("still flags overconfidence when the gap is >1", async () => {
    const { render } = await import("@testing-library/react");
    const { CalibrationPlot } = await import("../components/trace/CalibrationPlot");
    const trace: import("../api/types").ThinkingTrace = {
      total_turns: 0,
      phase_breakdown: { clarification: 0, decomposition: 0, solving: 0, wrap_up: 0 },
      subproblems: [],
      direct_answers_requested: 0,
      self_corrections: 0,
      initial_understanding: "",
      final_understanding: "",
      understanding_delta_label: "small",
      understanding_delta_evidence: "",
      calibration_points: [
        // Predicted 5, got wrong (mapped 1) → gap 4 → overconfident.
        { subproblem_id: "sp-1", predicted_confidence: 5, outcome: "wrong" },
        { subproblem_id: "sp-2", predicted_confidence: 5, outcome: "wrong" },
      ],
    };
    const { container } = render(<CalibrationPlot trace={trace} />);
    expect(container.textContent?.toLowerCase()).toContain("overconfident");
  });
});
