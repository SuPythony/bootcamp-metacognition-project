import { motion } from "framer-motion";
import type { ThinkingTrace } from "../../api/types";

interface CalibrationPlotProps {
  trace: ThinkingTrace;
}

const PLOT_HEIGHT = 128;

export function CalibrationPlot({ trace }: CalibrationPlotProps) {
  const points = trace.subproblems
    .map((sp) => ({
      id: sp.id,
      confidence: sp.confidence_score,
      direct: sp.direct_answer_requested,
    }))
    .filter((p) => p.confidence !== null && p.confidence !== undefined) as Array<{
    id: string;
    confidence: number;
    direct: boolean;
  }>;

  if (points.length === 0) return null;

  const avg = points.reduce((s, p) => s + p.confidence, 0) / points.length;
  const summary =
    avg >= 4
      ? "You felt sure of yourself most of the time."
      : avg >= 3
      ? "You held a balanced sense of confidence — useful calibration."
      : "You doubted yourself more than your work warranted.";

  return (
    <section className="space-y-3">
      <h3 className="font-display text-xl font-semibold text-ink">
        How confident did you feel?
      </h3>
      <div className="bg-surface border border-rule rounded-md p-4">
        <div className="flex">
          {/* y-axis labels */}
          <div
            className="flex flex-col justify-between pr-3 text-caption text-ink-faint font-mono text-mono"
            style={{ height: PLOT_HEIGHT }}
            aria-hidden
          >
            <span>5</span>
            <span>3</span>
            <span>1</span>
          </div>
          {/* plot area */}
          <div className="flex-1 relative">
            {/* gridlines */}
            <div
              className="absolute inset-0 flex flex-col justify-between"
              aria-hidden
            >
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="h-px bg-rule/60" />
              ))}
            </div>
            {/* bars */}
            <div
              className="relative flex items-end gap-3 border-l border-rule pl-2"
              style={{ height: PLOT_HEIGHT }}
            >
              {points.map((p, i) => {
                const heightPx = Math.max(2, (p.confidence / 5) * PLOT_HEIGHT);
                return (
                  <div
                    key={p.id}
                    className="flex-1 flex justify-center min-w-0"
                    title={`${p.id}: ${p.confidence}/5`}
                  >
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: heightPx }}
                      transition={{
                        duration: 0.5,
                        delay: 0.1 + i * 0.06,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                      className={`w-full max-w-[42px] rounded-t-md ${
                        p.direct ? "bg-hint/70" : "bg-calibrate/80"
                      }`}
                      aria-label={`${p.id}: ${p.confidence} of 5 confidence`}
                    />
                  </div>
                );
              })}
            </div>
            {/* x-axis labels */}
            <div className="flex gap-3 pl-2 mt-2">
              {points.map((p) => (
                <div
                  key={p.id}
                  className="flex-1 text-center font-mono text-[10px] text-ink-faint truncate"
                >
                  {p.id}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-4 text-caption text-ink-faint">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-calibrate/80" />
            self-solved
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-hint/70" />
            asked for answer
          </span>
        </div>
      </div>
      <p className="text-caption text-ink-soft italic">{summary}</p>
    </section>
  );
}
