import { describe, it, expect } from "vitest";
import { wrapInlineMath } from "../../../specializations/math/AlgebraSteps";

describe("wrapInlineMath", () => {
  it("wraps a plain expression in single-$ delimiters", () => {
    expect(wrapInlineMath("x^2 + 1")).toBe("$x^2 + 1$");
  });

  it("strips a pre-existing single $ wrapper", () => {
    expect(wrapInlineMath("$x^2$")).toBe("$x^2$");
  });

  it("strips pre-existing $$ wrappers", () => {
    expect(wrapInlineMath("$$x^2$$")).toBe("$x^2$");
  });

  it("escapes inner $ so delimiter pairing remains balanced", () => {
    // Defensive: sympy.latex shouldn't emit raw $, but if it does we
    // must not break the outer $...$ pair (which would corrupt the markdown).
    expect(wrapInlineMath("a $ b")).toBe("$a \\$ b$");
  });

  it("handles empty input", () => {
    expect(wrapInlineMath("")).toBe("$$");
  });
});
