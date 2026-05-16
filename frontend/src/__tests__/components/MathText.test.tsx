import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MathText from "../../components/MathText";

describe("MathText — plain text", () => {
  it("renders plain text unchanged", () => {
    const { container } = render(<MathText>Hello world</MathText>);
    expect(container.textContent).toContain("Hello world");
  });

  it("does not produce .katex spans for plain text", () => {
    const { container } = render(<MathText>No math here</MathText>);
    expect(container.querySelector(".katex")).toBeNull();
  });
});

describe("MathText — inline math ($...$)", () => {
  it("strips dollar-sign delimiters from inline math", () => {
    const { container } = render(<MathText>{"$x^2$"}</MathText>);
    expect(container.textContent).not.toContain("$");
  });

  it("produces a .katex element for inline math", () => {
    const { container } = render(<MathText>{"$x^2$"}</MathText>);
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("renders a fraction without raw dollar signs", () => {
    const { container } = render(
      <MathText>{"$\\frac{-b}{2a}$"}</MathText>
    );
    expect(container.textContent).not.toContain("$");
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("renders the quadratic formula inline", () => {
    const { container } = render(
      <MathText>{"$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$"}</MathText>
    );
    expect(container.textContent).not.toContain("$");
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("renders mixed text and inline math", () => {
    const { container } = render(
      <MathText>{"The radius is $r^2$ squared."}</MathText>
    );
    expect(container.textContent).not.toContain("$");
    expect(container.textContent).toContain("radius");
    expect(container.textContent).toContain("squared");
    expect(container.querySelector(".katex")).not.toBeNull();
  });
});

describe("MathText — display math ($$...$$)", () => {
  // remark-math requires $$ on its own line (paragraph boundary) for block/display math
  const displayMath = "\n$$\nx = \\frac{-b}{2a}\n$$\n";

  it("strips double-dollar delimiters from display math", () => {
    const { container } = render(<MathText>{displayMath}</MathText>);
    expect(container.textContent).not.toContain("$");
  });

  it("produces a .katex-display element for display math", () => {
    const { container } = render(<MathText>{displayMath}</MathText>);
    expect(container.querySelector(".katex-display")).not.toBeNull();
  });
});

describe("MathText — inline prop", () => {
  it("wraps output in <span>, not <p>, when inline=true", () => {
    const { container } = render(
      <MathText inline>{"$x^2 + y^2 = r^2$"}</MathText>
    );
    expect(container.querySelector("p")).toBeNull();
  });

  it("still renders math correctly with inline=true", () => {
    const { container } = render(
      <MathText inline>{"$x^2$"}</MathText>
    );
    expect(container.textContent).not.toContain("$");
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("wraps paragraph content in <p> when inline is not set", () => {
    const { container } = render(<MathText>{"Some text"}</MathText>);
    expect(container.querySelector("p")).not.toBeNull();
  });
});

describe("MathText — null / undefined children", () => {
  it("renders empty without crashing when children is null", () => {
    const { container } = render(
      <MathText>{null as unknown as string}</MathText>
    );
    expect(container.textContent).toBe("");
  });

  it("renders empty without crashing when children is undefined", () => {
    const { container } = render(
      <MathText>{undefined as unknown as string}</MathText>
    );
    expect(container.textContent).toBe("");
  });

  it("renders empty without crashing on empty string", () => {
    const { container } = render(<MathText>{""}</MathText>);
    expect(container.textContent).toBe("");
  });

  it("does not crash with inline + null", () => {
    const { container } = render(
      <MathText inline>{null as unknown as string}</MathText>
    );
    expect(container.textContent).toBe("");
  });
});

describe("MathText — RuleRecallPrompt rule strings", () => {
  // These are the exact strings the math agent sends in candidate_rules
  const rules = [
    "$a(b + c) = ab + ac$ (distributive)",
    "$a + b = b + a$ (commutative)",
    "$a^m \\cdot a^n = a^{m+n}$ (power rule)",
  ];

  it.each(rules)("renders rule '%s' without raw dollar signs", (rule) => {
    const { container } = render(<MathText inline>{rule}</MathText>);
    expect(container.textContent).not.toContain("$");
    expect(container.querySelector(".katex")).not.toBeNull();
  });
});
