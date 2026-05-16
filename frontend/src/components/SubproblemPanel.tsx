import { AnimatePresence, motion } from "framer-motion";
import type { Subproblem } from "../api/types";
import HintBadge from "./HintBadge";
import MathText from "./MathText";

const STATUS_CARD: Record<Subproblem["status"], string> = {
  pending: "bg-surface border-rule",
  active:
    "bg-surface border-solved ring-1 ring-solved/40 shadow-[0_0_0_4px_rgb(var(--color-solved)/0.12)]",
  solved: "bg-surface border-rule",
};

const STATUS_LABEL_TONE: Record<Subproblem["status"], string> = {
  pending: "text-ink-faint",
  active: "text-solved",
  solved: "text-solved",
};

const STATUS_LABEL: Record<Subproblem["status"], string> = {
  pending: "Pending",
  active: "Working…",
  solved: "Solved",
};

function StatusGlyph({ status }: { status: Subproblem["status"] }) {
  if (status === "solved") {
    return (
      <span
        className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-solved text-paper"
        aria-label="solved"
      >
        <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" aria-hidden>
          <path
            d="M2.5 6.2 L5 8.5 L9.5 3.8"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      </span>
    );
  }
  if (status === "active") {
    return (
      <motion.span
        animate={{ opacity: [0.55, 1, 0.55] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        className="inline-flex h-4 w-4 items-center justify-center"
        aria-label="active"
      >
        <span className="block h-3 w-3 rounded-full bg-solved/30 border border-solved" />
      </motion.span>
    );
  }
  return (
    <span
      className="inline-flex h-4 w-4 items-center justify-center"
      aria-label="pending"
    >
      <span className="block h-3 w-3 rounded-full border border-rule bg-paper" />
    </span>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-3 space-y-3">
      <svg viewBox="0 0 80 80" className="w-16 h-16 text-rule" aria-hidden>
        <circle cx="40" cy="20" r="6" fill="none" stroke="currentColor" strokeWidth="1.2" />
        <circle
          cx="20"
          cy="50"
          r="5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeDasharray="2 2"
        />
        <circle
          cx="60"
          cy="50"
          r="5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeDasharray="2 2"
        />
        <path
          d="M40 26 L40 38 M40 38 L20 45 M40 38 L60 45"
          stroke="currentColor"
          strokeWidth="1.2"
          fill="none"
        />
      </svg>
      <p className="text-caption text-ink-faint italic max-w-[16ch]">
        Your breakdown will grow here.
      </p>
    </div>
  );
}

export default function SubproblemPanel({
  subproblems,
}: {
  subproblems: Subproblem[];
}) {
  const hasItems = subproblems.length > 0;

  return (
    <aside
      data-testid="subproblem-panel"
      className="w-80 border-l border-rule bg-paper flex flex-col"
    >
      <div className="px-4 py-3 border-b border-rule">
        <h2 className="text-label text-ink-faint">Problem Breakdown</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {!hasItems ? (
          <EmptyState />
        ) : (
          <div className="relative">
            <span
              className="absolute left-2 top-4 bottom-4 w-px bg-rule"
              aria-hidden
            />
            <ul className="space-y-3">
              <AnimatePresence initial={false}>
                {subproblems.map((sp) => (
                  <motion.li
                    key={sp.id}
                    layout
                    initial={{ opacity: 0, x: -8, scale: 0.98 }}
                    animate={{
                      opacity: 1,
                      x: 0,
                      scale: sp.status === "active" ? 1.02 : 1,
                    }}
                    exit={{ opacity: 0, x: -8, scale: 0.98 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                    className="relative flex items-start gap-3 pl-0"
                  >
                    <span className="relative z-10 mt-3 shrink-0 bg-paper">
                      <StatusGlyph status={sp.status} />
                    </span>

                    <div
                      className={`flex-1 min-w-0 rounded-md border p-3 transition-all ${STATUS_CARD[sp.status]}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="font-mono text-mono text-ink-soft">
                          {sp.id}
                        </span>
                        <div className="flex items-center gap-2">
                          {sp.hints_given > 0 && <HintBadge count={sp.hints_given} />}
                          <span
                            className={`text-label ${STATUS_LABEL_TONE[sp.status]}`}
                          >
                            {STATUS_LABEL[sp.status]}
                          </span>
                        </div>
                      </div>
                      <p className="text-body text-ink leading-snug">
                        <MathText inline>{sp.description}</MathText>
                      </p>
                      {sp.goal && (
                        <p className="text-caption text-ink-faint mt-1.5 italic">
                          → <MathText inline>{sp.goal}</MathText>
                        </p>
                      )}
                    </div>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </div>
        )}
      </div>
    </aside>
  );
}
