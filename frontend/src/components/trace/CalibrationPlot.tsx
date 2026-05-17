import { motion } from "framer-motion";
import type { ThinkingTrace } from "../../api/types";

interface CalibrationPlotProps {
  trace: ThinkingTrace;
}

// Plot calibration_points (predicted-vs-outcome) as a scatter. x-axis is the
// predicted confidence (1..5); y-axis encodes outcome (correct=5, partial=3,
// wrong=1). A dashed diagonal marks perfect calibration. Points above the
// line = underconfident; below = overconfident.
const OUTCOME_Y: Record<NonNullable<NonNullable<ThinkingTrace["calibration_points"]>[number]["outcome"]>, number> = {
  correct: 5,
  partial: 3,
  wrong: 1,
};

const OUTCOME_FILL: Record<NonNullable<NonNullable<ThinkingTrace["calibration_points"]>[number]["outcome"]>, string> = {
  correct: "rgb(var(--color-solved))",
  partial: "rgb(var(--color-hint))",
  wrong: "rgb(var(--color-alarm))",
};

const PLOT_SIZE = 220;
const PAD = 28; // padding around the plot for axis labels

// Calibration tolerates a 1-step gap between predicted confidence (1..5) and
// the mapped outcome (correct=5, partial=3, wrong=1). Strict equality
// mislabels predicting 4 then getting it right as "underconfident" — that
// single-point gap is well within calibration. Anything further than 1
// counts as over- or under-confident.
function classify(predicted: number, actual: number): "calibrated" | "over" | "under" {
  const gap = predicted - actual;
  if (Math.abs(gap) <= 1) return "calibrated";
  return gap > 0 ? "over" : "under";
}

function buildSummary(
  points: Array<{ predicted: number; outcome: "correct" | "partial" | "wrong" }>,
): string {
  if (points.length === 0) return "";
  let over = 0;
  let under = 0;
  let calibrated = 0;
  for (const p of points) {
    const tag = classify(p.predicted, OUTCOME_Y[p.outcome]);
    if (tag === "over") over += 1;
    else if (tag === "under") under += 1;
    else calibrated += 1;
  }
  if (calibrated >= over + under) {
    return "Your gut and your accuracy lined up most of the time — that's calibration.";
  }
  if (over > under) {
    return "You leaned overconfident — predictions sat above outcomes more often than not.";
  }
  return "You leaned underconfident — you knew more than your predictions said.";
}

export function CalibrationPlot({ trace }: CalibrationPlotProps) {
  const raw = trace.calibration_points ?? [];
  const points = raw
    .filter(
      (p): p is { subproblem_id: string; predicted_confidence: number; outcome: "correct" | "partial" | "wrong" } =>
        p.outcome === "correct" || p.outcome === "partial" || p.outcome === "wrong",
    )
    .map((p) => ({
      id: p.subproblem_id,
      predicted: p.predicted_confidence,
      outcome: p.outcome,
    }));

  if (points.length === 0) return null;

  // Coordinate mapping: confidence 1..5 → 0..PLOT_SIZE.
  const scale = (v: number) => ((v - 1) / 4) * PLOT_SIZE;
  const totalSize = PLOT_SIZE + PAD * 2;

  const summary = buildSummary(
    points.map((p) => ({ predicted: p.predicted, outcome: p.outcome })),
  );

  return (
    <section className="space-y-3">
      <h3 className="font-display text-xl font-semibold text-ink">
        Predicted vs. actual
      </h3>
      <div className="bg-surface border border-rule rounded-md p-4">
        <div className="flex justify-center">
          <svg
            width={totalSize}
            height={totalSize}
            viewBox={`0 0 ${totalSize} ${totalSize}`}
            role="img"
            aria-label="Calibration scatter — predicted confidence vs actual outcome"
          >
            {/* gridlines */}
            {[1, 2, 3, 4, 5].map((v) => (
              <g key={`g-${v}`}>
                <line
                  x1={PAD + scale(v)}
                  y1={PAD}
                  x2={PAD + scale(v)}
                  y2={PAD + PLOT_SIZE}
                  stroke="rgb(var(--color-rule))"
                  strokeWidth="0.6"
                  opacity="0.6"
                />
                <line
                  x1={PAD}
                  y1={PAD + PLOT_SIZE - scale(v)}
                  x2={PAD + PLOT_SIZE}
                  y2={PAD + PLOT_SIZE - scale(v)}
                  stroke="rgb(var(--color-rule))"
                  strokeWidth="0.6"
                  opacity="0.6"
                />
              </g>
            ))}

            {/* y=x perfect-calibration diagonal */}
            <line
              x1={PAD}
              y1={PAD + PLOT_SIZE}
              x2={PAD + PLOT_SIZE}
              y2={PAD}
              stroke="rgb(var(--color-ink-faint))"
              strokeWidth="0.8"
              strokeDasharray="3 3"
              opacity="0.8"
            />

            {/* axis labels — x */}
            {[1, 2, 3, 4, 5].map((v) => (
              <text
                key={`xl-${v}`}
                x={PAD + scale(v)}
                y={PAD + PLOT_SIZE + 16}
                textAnchor="middle"
                fontSize="10"
                fontFamily="ui-monospace, monospace"
                fill="rgb(var(--color-ink-faint))"
              >
                {v}
              </text>
            ))}
            {/* y labels — confidence-equivalent (5/3/1 = correct/partial/wrong) */}
            {[
              { v: 5, label: "✓" },
              { v: 3, label: "~" },
              { v: 1, label: "✗" },
            ].map(({ v, label }) => (
              <text
                key={`yl-${v}`}
                x={PAD - 8}
                y={PAD + PLOT_SIZE - scale(v) + 4}
                textAnchor="end"
                fontSize="10"
                fontFamily="ui-monospace, monospace"
                fill="rgb(var(--color-ink-faint))"
              >
                {label}
              </text>
            ))}

            {/* axis titles */}
            <text
              x={PAD + PLOT_SIZE / 2}
              y={totalSize - 4}
              textAnchor="middle"
              fontSize="10"
              fill="rgb(var(--color-ink-faint))"
            >
              predicted confidence
            </text>
            <text
              x={10}
              y={PAD + PLOT_SIZE / 2}
              textAnchor="middle"
              fontSize="10"
              fill="rgb(var(--color-ink-faint))"
              transform={`rotate(-90, 10, ${PAD + PLOT_SIZE / 2})`}
            >
              actual outcome
            </text>

            {/* scatter points */}
            {points.map((p, i) => {
              const cx = PAD + scale(p.predicted);
              const cy = PAD + PLOT_SIZE - scale(OUTCOME_Y[p.outcome]);
              return (
                <motion.g
                  key={`pt-${i}-${p.id}`}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{
                    duration: 0.35,
                    delay: 0.1 + i * 0.07,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                >
                  <circle
                    cx={cx}
                    cy={cy}
                    r="6"
                    fill={OUTCOME_FILL[p.outcome]}
                    opacity="0.85"
                    stroke="rgb(var(--color-paper))"
                    strokeWidth="1.5"
                  >
                    <title>{`${p.id}: predicted ${p.predicted}/5, ${p.outcome}`}</title>
                  </circle>
                  <text
                    x={cx + 10}
                    y={cy + 3}
                    fontSize="9"
                    fontFamily="ui-monospace, monospace"
                    fill="rgb(var(--color-ink-soft))"
                  >
                    {p.id}
                  </text>
                </motion.g>
              );
            })}
          </svg>
        </div>

        {/* legend */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-ink-faint">
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: "rgb(var(--color-solved))" }}
            />
            correct
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: "rgb(var(--color-hint))" }}
            />
            partial
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: "rgb(var(--color-alarm))" }}
            />
            wrong
          </span>
          <span className="flex items-center gap-1.5 ml-auto">
            <span className="inline-block w-4 h-px border-t border-dashed border-ink-faint" />
            perfect calibration
          </span>
        </div>
      </div>
      <p className="text-caption text-ink-soft italic">{summary}</p>
    </section>
  );
}
