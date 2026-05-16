import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { lookup, has } from "../../specializations/registry";

describe("specializations registry", () => {
  it("resolves general.CalibrationCheck", () => {
    expect(has("general.CalibrationCheck")).toBe(true);
    expect(lookup("general.CalibrationCheck")).toBeDefined();
  });

  it("resolves general.ConfidenceWidget — must be registered to avoid soft-lock", () => {
    expect(has("general.ConfidenceWidget")).toBe(true);
    expect(lookup("general.ConfidenceWidget")).toBeDefined();
  });

  it("resolves general.ReflectionPrompt", () => {
    expect(has("general.ReflectionPrompt")).toBe(true);
    expect(lookup("general.ReflectionPrompt")).toBeDefined();
  });

  it("resolves math.RuleRecallPrompt", () => {
    expect(has("math.RuleRecallPrompt")).toBe(true);
  });

  describe("unknown component", () => {
    let warnSpy: ReturnType<typeof vi.spyOn>;
    beforeEach(() => {
      warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    });
    afterEach(() => {
      warnSpy.mockRestore();
    });

    it("returns undefined for unknown key", () => {
      expect(lookup("math.NotAComponent")).toBeUndefined();
      expect(has("math.NotAComponent")).toBe(false);
    });

    it("logs a warning for unknown key", () => {
      lookup("math.NotAComponent");
      expect(warnSpy).toHaveBeenCalled();
    });
  });
});
