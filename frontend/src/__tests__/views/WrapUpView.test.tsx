import { render, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import WrapUpView from "../../views/WrapUpView";
import { api } from "../../api/client";
import { ThemeProvider } from "../../components/theme/ThemeProvider";

function wrap(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("WrapUpView", () => {
  let traceSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    traceSpy = vi.spyOn(api, "thinkingTrace");
  });

  afterEach(() => {
    traceSpy.mockRestore();
  });

  it("shows restart button after trace loads successfully", async () => {
    traceSpy.mockResolvedValue({
      total_turns: 4,
      phase_breakdown: { clarification: 1, decomposition: 1, solving: 1, wrap_up: 1 },
      subproblems: [],
      direct_answers_requested: 0,
      self_corrections: 0,
      initial_understanding: "",
      final_understanding: "",
      understanding_delta_label: "small",
      understanding_delta_evidence: "",
    });
    const onRestart = vi.fn();
    const { findByText } = wrap(<WrapUpView sessionId="s1" onRestart={onRestart} />);
    const btn = await findByText("Start a new session");
    fireEvent.click(btn);
    expect(onRestart).toHaveBeenCalledTimes(1);
  });

  it("renders restart button when trace request errors (no dead-end)", async () => {
    traceSpy.mockRejectedValue(new Error("backend down"));
    const onRestart = vi.fn();
    const { findByText } = wrap(<WrapUpView sessionId="s2" onRestart={onRestart} />);
    const btn = await findByText("Start a new session");
    fireEvent.click(btn);
    expect(onRestart).toHaveBeenCalledTimes(1);
  });

  it("shows the error message when trace request errors", async () => {
    traceSpy.mockRejectedValue(new Error("backend down"));
    const { findByText } = wrap(<WrapUpView sessionId="s3" onRestart={() => {}} />);
    await findByText(/backend down/i);
  });

  it("does not show restart button while loading", async () => {
    let resolve!: (v: unknown) => void;
    traceSpy.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }) as never,
    );
    const { queryByText } = wrap(<WrapUpView sessionId="s4" onRestart={() => {}} />);
    expect(queryByText("Start a new session")).toBeNull();
    resolve({
      total_turns: 1,
      phase_breakdown: { clarification: 1, decomposition: 0, solving: 0, wrap_up: 0 },
      subproblems: [],
      direct_answers_requested: 0,
      self_corrections: 0,
      initial_understanding: "",
      final_understanding: "",
      understanding_delta_label: "small",
      understanding_delta_evidence: "",
    });
    await waitFor(() => expect(queryByText("Start a new session")).not.toBeNull());
  });
});
