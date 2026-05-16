import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CalibrationPlot } from "../../../components/trace/CalibrationPlot";
import type { ThinkingTrace } from "../../../api/types";

function baseTrace(
  cp: ThinkingTrace["calibration_points"],
): ThinkingTrace {
  return {
    total_turns: 0,
    phase_breakdown: { clarification: 0, decomposition: 0, solving: 0, wrap_up: 0 },
    subproblems: [],
    direct_answers_requested: 0,
    self_corrections: 0,
    initial_understanding: "",
    final_understanding: "",
    understanding_delta_label: "small",
    understanding_delta_evidence: "",
    calibration_points: cp,
  };
}

describe("CalibrationPlot", () => {
  it("renders nothing when calibration_points is missing", () => {
    const { container } = render(<CalibrationPlot trace={baseTrace(undefined)} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when all outcomes are null", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 4, outcome: null },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a scatter for points with valid outcomes", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 5, outcome: "correct" as const },
      { subproblem_id: "sp-2", predicted_confidence: 2, outcome: "wrong" as const },
      { subproblem_id: "sp-3", predicted_confidence: 3, outcome: "partial" as const },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBe(3);
    expect(container.querySelector("h3")?.textContent).toContain("Predicted");
  });

  it("filters out null-outcome rows but keeps valid ones", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 4, outcome: "correct" as const },
      { subproblem_id: "sp-2", predicted_confidence: 3, outcome: null },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    expect(container.querySelectorAll("circle").length).toBe(1);
  });

  it("includes a legend for correct / partial / wrong", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 5, outcome: "correct" as const },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    expect(container.textContent).toContain("correct");
    expect(container.textContent).toContain("partial");
    expect(container.textContent).toContain("wrong");
    expect(container.textContent).toContain("perfect calibration");
  });

  it("shows an overconfident summary when predictions exceed outcomes", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 5, outcome: "wrong" as const },
      { subproblem_id: "sp-2", predicted_confidence: 4, outcome: "wrong" as const },
      { subproblem_id: "sp-3", predicted_confidence: 5, outcome: "partial" as const },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    expect(container.textContent?.toLowerCase()).toContain("overconfident");
  });

  it("shows an underconfident summary when outcomes exceed predictions", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 1, outcome: "correct" as const },
      { subproblem_id: "sp-2", predicted_confidence: 2, outcome: "correct" as const },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    expect(container.textContent?.toLowerCase()).toContain("underconfident");
  });

  it("shows a calibrated summary when predictions match outcomes", () => {
    const cp = [
      { subproblem_id: "sp-1", predicted_confidence: 5, outcome: "correct" as const },
      { subproblem_id: "sp-2", predicted_confidence: 1, outcome: "wrong" as const },
    ];
    const { container } = render(<CalibrationPlot trace={baseTrace(cp)} />);
    expect(container.textContent?.toLowerCase()).toContain("calibration");
  });
});
