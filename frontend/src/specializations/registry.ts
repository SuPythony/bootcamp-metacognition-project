// Single source for "<domain>.<component>" → React component lookup.
// Names here must match entries in each domain's manifest.json `ui_components` list.
// Missing names log a warning and render a fallback — the chat must still proceed.

import type { ComponentType } from "react";

import * as math from "./math";
import * as programming from "./programming";
import * as essay from "./essay";
import * as science from "./science";
import CalibrationCheck from "../components/CalibrationCheck";
import ConfidenceWidget from "../components/ConfidenceWidget";
import ReflectionPrompt from "../components/ReflectionPrompt";

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
  // general (cross-domain)
  "general.CalibrationCheck": CalibrationCheck as ComponentType<AnyProps>,
  "general.ConfidenceWidget": ConfidenceWidget as ComponentType<AnyProps>,
  "general.ReflectionPrompt": ReflectionPrompt as ComponentType<AnyProps>,
};

// Surface a missing component once per process; suppress duplicate warnings so
// the console isn't spammed every render for the same key.
const _warned = new Set<string>();
export function lookup(key: string): ComponentType<AnyProps> | undefined {
  const c = registry[key];
  if (!c && !_warned.has(key)) {
    _warned.add(key);
    console.warn(`[specializations] no component for "${key}"`);
  }
  return c;
}

// Silent existence check — does not log when missing. Use this for hot probes
// (e.g. SessionView.isAwaitingDirective) that run on every render.
export function has(key: string): boolean {
  return key in registry;
}

// Test helper: reset the once-per-process dedup so each test exercises the
// warn path freshly. Do NOT call from production code.
export function _resetLookupWarningsForTests(): void {
  _warned.clear();
}
