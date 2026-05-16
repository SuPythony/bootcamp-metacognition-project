import { motion } from "framer-motion";
import type { ThinkingTrace } from "../../api/types";

interface NumberCellProps {
  value: number;
  label: string;
  tone?: "ink" | "solved" | "hint";
  delay?: number;
}

const TONES: Record<NonNullable<NumberCellProps["tone"]>, string> = {
  ink: "text-ink",
  solved: "text-solved",
  hint: "text-hint",
};

function NumberCell({ value, label, tone = "ink", delay = 0 }: NumberCellProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      className="flex flex-col items-start gap-1"
    >
      <span
        className={`font-display font-semibold leading-none text-[3rem] tracking-tight ${TONES[tone]}`}
      >
        {value}
      </span>
      <span className="text-caption text-ink-faint leading-tight max-w-[12ch]">
        {label}
      </span>
    </motion.div>
  );
}

export function TraceNumbers({ trace }: { trace: ThinkingTrace }) {
  const safe = (n: unknown) => (typeof n === "number" ? n : 0);
  const cells: NumberCellProps[] = [
    { value: safe(trace.total_turns), label: "turns" },
    { value: trace.subproblems?.length ?? 0, label: "parts you broke it into" },
    { value: safe(trace.self_corrections), label: "times you changed your mind", tone: "solved" },
    { value: safe(trace.direct_answers_requested), label: "answers you asked for", tone: "hint" },
  ];

  return (
    <section className="space-y-3">
      <h3 className="font-display text-xl font-semibold text-ink">By the numbers</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 border-t border-b border-rule py-5">
        {cells.map((c, i) => (
          <NumberCell key={c.label} {...c} delay={0.05 * i} />
        ))}
      </div>
    </section>
  );
}
