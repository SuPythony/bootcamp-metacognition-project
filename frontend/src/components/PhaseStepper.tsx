import { Check } from "lucide-react";
import type { Phase } from "../api/types";

const PHASES: Array<{ key: Phase; label: string; description: string }> = [
  {
    key: "clarification",
    label: "Clarify",
    description: "What's your current thinking?",
  },
  {
    key: "decomposition",
    label: "Break down",
    description: "Split the problem into parts.",
  },
  {
    key: "solving",
    label: "Solve",
    description: "Work through it step by step.",
  },
  {
    key: "wrap_up",
    label: "Wrap up",
    description: "Look back at the shift.",
  },
];

type StepState = "pending" | "active" | "done";

function stateForIndex(activeIndex: number, i: number): StepState {
  if (i < activeIndex) return "done";
  if (i === activeIndex) return "active";
  return "pending";
}

export default function PhaseStepper({
  phase,
  orientation = "horizontal",
}: {
  phase: Phase;
  orientation?: "horizontal" | "vertical";
}) {
  const activeIndex = PHASES.findIndex((p) => p.key === phase);
  const isHorizontal = orientation === "horizontal";

  return (
    <ol
      data-testid="phase-stepper"
      className={`flex items-center ${
        isHorizontal ? "flex-row gap-2" : "flex-col gap-3"
      }`}
      aria-label="Session phase"
    >
      {PHASES.map((p, i) => {
        const state = stateForIndex(activeIndex < 0 ? 0 : activeIndex, i);
        return (
          <li
            key={p.key}
            className="flex items-center gap-2 group relative"
            aria-current={state === "active" ? "step" : undefined}
          >
            <Node state={state} index={i} />
            <span
              className={`text-label transition-colors ${
                state === "active"
                  ? "text-ink"
                  : state === "done"
                  ? "text-ink-soft"
                  : "text-ink-faint"
              }`}
            >
              {p.label}
            </span>
            {i < PHASES.length - 1 && (
              <span
                className={`h-px w-6 ${
                  state === "done" ? "bg-ink-soft" : "bg-rule"
                }`}
                aria-hidden
              />
            )}
            <span
              role="tooltip"
              className="pointer-events-none absolute top-full left-1/2 -translate-x-1/2 mt-2 px-2 py-1 rounded-md bg-ink text-paper text-caption whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-10"
            >
              {p.description}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function Node({ state, index }: { state: StepState; index: number }) {
  const ring =
    state === "done"
      ? "bg-ink-soft border-ink-soft text-paper"
      : state === "active"
      ? "bg-accent border-accent text-white"
      : "bg-paper border-rule text-ink-faint";

  return (
    <span
      className={`inline-flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-mono ${ring}`}
    >
      {state === "done" ? <Check size={11} strokeWidth={2.5} /> : index + 1}
    </span>
  );
}
