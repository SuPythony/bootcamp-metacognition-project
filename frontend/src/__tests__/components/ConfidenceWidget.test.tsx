import { render, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ConfidenceWidget from "../../components/ConfidenceWidget";

describe("ConfidenceWidget", () => {
  it("renders five buttons labelled 1-5", () => {
    const { getAllByRole } = render(<ConfidenceWidget onSelect={() => {}} />);
    const buttons = getAllByRole("button");
    expect(buttons).toHaveLength(5);
    expect(buttons.map((b) => b.textContent?.trim()[0])).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
    ]);
  });

  it("calls onSelect with the picked value", () => {
    const onSelect = vi.fn();
    const { getAllByRole } = render(<ConfidenceWidget onSelect={onSelect} />);
    fireEvent.click(getAllByRole("button")[2]); // value 3
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(3);
  });

  it("locks after the first pick — second click does not fire onSelect", () => {
    const onSelect = vi.fn();
    const { getAllByRole } = render(<ConfidenceWidget onSelect={onSelect} />);
    const buttons = getAllByRole("button");
    fireEvent.click(buttons[0]); // value 1
    fireEvent.click(buttons[4]); // value 5
    fireEvent.click(buttons[2]); // value 3
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("disables all buttons after pick", () => {
    const { getAllByRole } = render(<ConfidenceWidget onSelect={() => {}} />);
    const buttons = getAllByRole("button") as HTMLButtonElement[];
    fireEvent.click(buttons[1]);
    buttons.forEach((b) => expect(b.disabled).toBe(true));
  });

  it("marks the picked button as aria-pressed", () => {
    const { getAllByRole } = render(<ConfidenceWidget onSelect={() => {}} />);
    const buttons = getAllByRole("button");
    fireEvent.click(buttons[3]); // value 4
    expect(buttons[3].getAttribute("aria-pressed")).toBe("true");
    expect(buttons[0].getAttribute("aria-pressed")).toBe("false");
  });
});
