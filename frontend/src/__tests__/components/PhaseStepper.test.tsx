import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import PhaseStepper from "../../components/PhaseStepper";
import type { Phase } from "../../api/types";

function activeStep(container: HTMLElement): HTMLElement | null {
  return container.querySelector('li[aria-current="step"]') as HTMLElement | null;
}

describe("PhaseStepper", () => {
  it("marks the clarification step active for phase=clarification", () => {
    const { container } = render(<PhaseStepper phase="clarification" />);
    expect(activeStep(container)?.textContent).toContain("Clarify");
  });

  it("marks the wrap_up step active for phase=wrap_up", () => {
    const { container } = render(<PhaseStepper phase="wrap_up" />);
    expect(activeStep(container)?.textContent).toContain("Wrap up");
  });

  it("renders no active step when phase is unknown — does NOT clamp to first", () => {
    const { container } = render(
      <PhaseStepper phase={"mystery_phase" as Phase} />,
    );
    expect(activeStep(container)).toBeNull();
  });
});
