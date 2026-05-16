import { describe, it, expect } from "vitest";
import {
  isAwaitingDirective,
  INTERACTIVE_DIRECTIVES,
  mergeSidePanelDirectives,
  normalizeDirective,
  directiveKey,
  getActiveSubproblemId,
} from "../../views/SessionView";
import type { ChatMessage } from "../../components/ChatPane";
import type { UIDirective, Subproblem } from "../../api/types";

function inline(component: string, domain = "general"): UIDirective {
  return {
    component,
    domain: domain as UIDirective["domain"],
    props: {},
    placement: "inline",
    lifetime: "until_next_turn",
  };
}

function sidePanel(
  component: string,
  props: Record<string, unknown> = {},
  domain = "math",
): UIDirective {
  return {
    component,
    domain: domain as UIDirective["domain"],
    props,
    placement: "side_panel",
    lifetime: "persistent_in_subproblem",
  };
}

const allKnown = () => true;
const noneKnown = () => false;

describe("isAwaitingDirective", () => {
  it("returns false on empty message list", () => {
    expect(isAwaitingDirective([], allKnown)).toBe(false);
  });

  it("returns false when last assistant has no directives", () => {
    const msgs: ChatMessage[] = [{ role: "assistant", content: "hi" }];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(false);
  });

  it("locks when an interactive directive (CalibrationCheck) is pending", () => {
    const msgs: ChatMessage[] = [
      { role: "assistant", content: "rate it", directives: [inline("CalibrationCheck")] },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(true);
  });

  it("locks for ConfidenceWidget", () => {
    const msgs: ChatMessage[] = [
      { role: "assistant", content: "?", directives: [inline("ConfidenceWidget")] },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(true);
  });

  it("locks for RuleRecallPrompt (math domain)", () => {
    const msgs: ChatMessage[] = [
      { role: "assistant", content: "?", directives: [inline("RuleRecallPrompt", "math")] },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(true);
  });

  it("does NOT lock for ReflectionPrompt (student types into chat)", () => {
    const msgs: ChatMessage[] = [
      { role: "assistant", content: "reflect", directives: [inline("ReflectionPrompt")] },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(false);
  });

  it("does NOT lock for display-only PseudocodePad", () => {
    const msgs: ChatMessage[] = [
      {
        role: "assistant",
        content: "scratch here",
        directives: [inline("PseudocodePad", "programming")],
      },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(false);
  });

  it("does NOT lock for display-only OutlineTree", () => {
    const msgs: ChatMessage[] = [
      {
        role: "assistant",
        content: "outline",
        directives: [inline("OutlineTree", "essay")],
      },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(false);
  });

  it("does NOT lock when the component is unknown (would soft-lock with no widget)", () => {
    const msgs: ChatMessage[] = [
      {
        role: "assistant",
        content: "?",
        directives: [inline("HallucinatedWidget")],
      },
    ];
    expect(isAwaitingDirective(msgs, noneKnown)).toBe(false);
  });

  it("locks only on the LAST assistant message's directives, not older ones", () => {
    const msgs: ChatMessage[] = [
      {
        role: "assistant",
        content: "first",
        directives: [inline("CalibrationCheck")],
      },
      { role: "user", content: "3" },
      { role: "assistant", content: "ack" },
    ];
    expect(isAwaitingDirective(msgs, allKnown)).toBe(false);
  });

  it("ignores side_panel and modal directives — only inline locks", () => {
    const sidePanel: UIDirective = {
      ...inline("CalibrationCheck"),
      placement: "side_panel",
    };
    const modal: UIDirective = {
      ...inline("CalibrationCheck"),
      placement: "modal",
    };
    expect(
      isAwaitingDirective(
        [{ role: "assistant", content: "?", directives: [sidePanel] }],
        allKnown,
      ),
    ).toBe(false);
    expect(
      isAwaitingDirective(
        [{ role: "assistant", content: "?", directives: [modal] }],
        allKnown,
      ),
    ).toBe(false);
  });
});

describe("mergeSidePanelDirectives", () => {
  it("returns prev unchanged when incoming is empty", () => {
    const prev = [sidePanel("RuleRecallPrompt", { ctx: "a" })];
    const result = mergeSidePanelDirectives(prev, []);
    expect(result).toBe(prev);
  });

  it("appends a fresh directive to prev", () => {
    const prev = [sidePanel("RuleRecallPrompt", { ctx: "a" })];
    const incoming = [sidePanel("GraphView", { url: "x" })];
    const result = mergeSidePanelDirectives(prev, incoming);
    expect(result).toHaveLength(2);
    expect(result[1].component).toBe("GraphView");
  });

  it("drops duplicate (component, props) — same component AND props", () => {
    const prev = [sidePanel("RuleRecallPrompt", { ctx: "a" })];
    const incoming = [sidePanel("RuleRecallPrompt", { ctx: "a" })];
    const result = mergeSidePanelDirectives(prev, incoming);
    expect(result).toBe(prev); // unchanged reference when nothing fresh
    expect(result).toHaveLength(1);
  });

  it("keeps same component with different props as distinct", () => {
    const prev = [sidePanel("RuleRecallPrompt", { ctx: "a" })];
    const incoming = [sidePanel("RuleRecallPrompt", { ctx: "b" })];
    const result = mergeSidePanelDirectives(prev, incoming);
    expect(result).toHaveLength(2);
  });

  it("merges across multiple turns without growing", () => {
    const d = sidePanel("RuleRecallPrompt", { ctx: "a" });
    let panel: UIDirective[] = [];
    panel = mergeSidePanelDirectives(panel, [d]);
    panel = mergeSidePanelDirectives(panel, [d]);
    panel = mergeSidePanelDirectives(panel, [d]);
    expect(panel).toHaveLength(1);
  });

  it("appends only the fresh subset when incoming is partial overlap", () => {
    const a = sidePanel("RuleRecallPrompt", { ctx: "a" });
    const b = sidePanel("GraphView", { url: "x" });
    const c = sidePanel("AlgebraSteps", { steps: [] });
    const prev = [a, b];
    const incoming = [a, c];
    const result = mergeSidePanelDirectives(prev, incoming);
    expect(result).toHaveLength(3);
    expect(result[2].component).toBe("AlgebraSteps");
  });
});

describe("normalizeDirective", () => {
  it("preserves a valid until_next_turn lifetime", () => {
    const d = inline("CalibrationCheck");
    expect(normalizeDirective(d).lifetime).toBe("until_next_turn");
    expect(normalizeDirective(d)).toBe(d); // same reference when no change
  });

  it("preserves until_dismissed", () => {
    const d: UIDirective = { ...inline("CalibrationCheck"), lifetime: "until_dismissed" };
    expect(normalizeDirective(d).lifetime).toBe("until_dismissed");
  });

  it("preserves persistent_in_subproblem", () => {
    const d: UIDirective = {
      ...inline("CalibrationCheck"),
      lifetime: "persistent_in_subproblem",
    };
    expect(normalizeDirective(d).lifetime).toBe("persistent_in_subproblem");
  });

  it("coerces an unknown lifetime to until_next_turn", () => {
    const d: UIDirective = {
      ...inline("CalibrationCheck"),
      lifetime: "forever" as UIDirective["lifetime"],
    };
    const result = normalizeDirective(d);
    expect(result.lifetime).toBe("until_next_turn");
    expect(result).not.toBe(d); // new object
  });

  it("coerces a missing lifetime to until_next_turn", () => {
    const d = {
      component: "CalibrationCheck",
      domain: "general",
      props: {},
      placement: "inline",
    } as unknown as UIDirective;
    expect(normalizeDirective(d).lifetime).toBe("until_next_turn");
  });
});

describe("directiveKey", () => {
  it("matches identical directives", () => {
    const a = inline("CalibrationCheck");
    const b = inline("CalibrationCheck");
    expect(directiveKey(a)).toBe(directiveKey(b));
  });

  it("differs by component name", () => {
    expect(directiveKey(inline("CalibrationCheck"))).not.toBe(
      directiveKey(inline("RuleRecallPrompt")),
    );
  });

  it("differs by props", () => {
    expect(directiveKey(sidePanel("X", { a: 1 }))).not.toBe(
      directiveKey(sidePanel("X", { a: 2 })),
    );
  });

  it("differs by placement", () => {
    const inlineX = inline("X");
    const panelX = { ...inlineX, placement: "side_panel" as const };
    expect(directiveKey(inlineX)).not.toBe(directiveKey(panelX));
  });
});

describe("getActiveSubproblemId", () => {
  const sp = (id: string, status: Subproblem["status"]): Subproblem => ({
    id,
    description: "",
    goal: "",
    status,
    hints_given: 0,
    direct_answer_requested: false,
  });

  it("returns null for empty list", () => {
    expect(getActiveSubproblemId([])).toBeNull();
  });

  it("returns null when no subproblem is active", () => {
    expect(
      getActiveSubproblemId([sp("sp-1", "solved"), sp("sp-2", "pending")]),
    ).toBeNull();
  });

  it("returns the id of the active subproblem", () => {
    expect(
      getActiveSubproblemId([
        sp("sp-1", "solved"),
        sp("sp-2", "active"),
        sp("sp-3", "pending"),
      ]),
    ).toBe("sp-2");
  });

  it("returns the first active id when multiple are marked active", () => {
    expect(
      getActiveSubproblemId([sp("sp-1", "active"), sp("sp-2", "active")]),
    ).toBe("sp-1");
  });
});

describe("INTERACTIVE_DIRECTIVES allowlist", () => {
  it("contains the three interactive widgets", () => {
    expect(INTERACTIVE_DIRECTIVES.has("CalibrationCheck")).toBe(true);
    expect(INTERACTIVE_DIRECTIVES.has("ConfidenceWidget")).toBe(true);
    expect(INTERACTIVE_DIRECTIVES.has("RuleRecallPrompt")).toBe(true);
  });

  it("excludes display-only / type-into-chat widgets", () => {
    expect(INTERACTIVE_DIRECTIVES.has("ReflectionPrompt")).toBe(false);
    expect(INTERACTIVE_DIRECTIVES.has("PseudocodePad")).toBe(false);
    expect(INTERACTIVE_DIRECTIVES.has("OutlineTree")).toBe(false);
  });
});
