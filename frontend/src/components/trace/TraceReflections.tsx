import { motion } from "framer-motion";
import type { ThinkingTrace } from "../../api/types";

const TRIGGER_LABEL: Record<string, string> = {
  periodic: "Mid-session",
  self_correction: "After a change of mind",
  escape_hatch: "After asking for help",
  wrap_up: "At the end",
};

const QUALITY_BADGE: Record<
  "shallow" | "decent" | "deep",
  { label: string; cls: string }
> = {
  shallow: {
    label: "shallow",
    cls: "text-amber-700 bg-amber-50 border-amber-200",
  },
  decent: {
    label: "decent",
    cls: "text-blue-700 bg-blue-50 border-blue-200",
  },
  deep: {
    label: "deep",
    cls: "text-solved bg-solved/10 border-solved/30",
  },
};

function truncate(s: string, max = 150): string {
  return s.length <= max ? s : s.slice(0, max).trimEnd() + "…";
}

function buildSummaryLine(
  reflectionSummary?: {
    deep_reflections: number;
    decent_reflections: number;
    shallow_reflections: number;
  },
): string | null {
  if (!reflectionSummary) return null;
  const parts: string[] = [];
  if (reflectionSummary.deep_reflections > 0)
    parts.push(`${reflectionSummary.deep_reflections} deep`);
  if (reflectionSummary.decent_reflections > 0)
    parts.push(`${reflectionSummary.decent_reflections} decent`);
  if (reflectionSummary.shallow_reflections > 0)
    parts.push(`${reflectionSummary.shallow_reflections} shallow`);
  if (parts.length === 0) return null;
  const total =
    (reflectionSummary.deep_reflections ?? 0) +
    (reflectionSummary.decent_reflections ?? 0) +
    (reflectionSummary.shallow_reflections ?? 0);
  return `${parts.join(", ")} reflection${total !== 1 ? "s" : ""} this session.`;
}

interface ReflectionCardProps {
  item: NonNullable<ThinkingTrace["reflection_prompts"]>[number];
  index: number;
}

function ReflectionCard({ item, index }: ReflectionCardProps) {
  const triggerLabel =
    TRIGGER_LABEL[item.trigger] ?? item.trigger;
  const badge =
    item.quality && item.quality in QUALITY_BADGE
      ? QUALITY_BADGE[item.quality as keyof typeof QUALITY_BADGE]
      : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
      className="bg-surface border border-rule rounded-md p-4 space-y-2"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-mono text-ink-faint">{triggerLabel}</span>
        {badge && (
          <span
            className={`text-label px-2 py-0.5 rounded-full border ${badge.cls}`}
          >
            {badge.label}
          </span>
        )}
      </div>
      <p className="text-body italic text-ink-soft leading-snug">
        "{item.question}"
      </p>
      {item.response && (
        <p className="text-body text-ink leading-snug">
          {truncate(item.response)}
        </p>
      )}
    </motion.div>
  );
}

export function TraceReflections({ trace }: { trace: ThinkingTrace }) {
  const prompts = trace.reflection_prompts ?? [];
  if (prompts.length === 0) return null;

  const summaryLine = buildSummaryLine(
    (trace as { reflection_summary?: Parameters<typeof buildSummaryLine>[0] })
      .reflection_summary,
  );

  return (
    <section className="space-y-3">
      <h3 className="font-display text-xl font-semibold text-ink">
        Your reflections
      </h3>
      <div className="space-y-3">
        {prompts.map((item, i) => (
          <ReflectionCard key={i} item={item} index={i} />
        ))}
      </div>
      {summaryLine && (
        <p className="text-caption text-ink-soft italic">{summaryLine}</p>
      )}
    </section>
  );
}
