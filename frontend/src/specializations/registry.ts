// Single source for "<domain>.<component>" → React component lookup.
// Names here must match entries in each domain's manifest.json `ui_components` list.
// Missing names log a warning and render a fallback — the chat must still proceed.

import type { ComponentType } from "react";

import * as math from "./math";
import * as programming from "./programming";
import * as essay from "./essay";
import * as science from "./science";

type AnyProps = Record<string, unknown>;

const registry: Record<string, ComponentType<AnyProps>> = {
  // math
  "math.AlgebraSteps": math.AlgebraSteps as ComponentType<AnyProps>,
  "math.GraphView": math.GraphView as ComponentType<AnyProps>,
  "math.RuleRecallPrompt": math.RuleRecallPrompt as ComponentType<AnyProps>,
  // programming
  "programming.CodeOutput": programming.CodeOutput as ComponentType<AnyProps>,
  "programming.PseudocodePad":
    programming.PseudocodePad as ComponentType<AnyProps>,
  // essay
  "essay.OutlineTree": essay.OutlineTree as ComponentType<AnyProps>,
  // science
  "science.GraphView": science.GraphView as ComponentType<AnyProps>,
  "science.DataTable": science.DataTable as ComponentType<AnyProps>,
};

export function lookup(key: string): ComponentType<AnyProps> | undefined {
  const c = registry[key];
  if (!c) console.warn(`[specializations] no component for "${key}"`);
  return c;
}

export function has(key: string): boolean {
  return key in registry;
}
