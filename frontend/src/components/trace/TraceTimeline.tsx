import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import {
  CheckCircle2,
  Lightbulb,
  KeyRound,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ThinkingTrace } from "../../api/types";
import MathText from "../MathText";

type EventKind = "solved" | "hint" | "escape" | "self_correction" | "summary";

interface TimelineEvent {
  kind: EventKind;
  caption: string;
  meta?: string;
  highlight?: boolean;
}

const ICONS: Record<EventKind, LucideIcon> = {
  solved: CheckCircle2,
  hint: Lightbulb,
  escape: KeyRound,
  self_correction: RotateCcw,
  summary: Sparkles,
};

const TONES: Record<EventKind, string> = {
  solved: "text-solved bg-solved/15 border-solved/40",
  hint: "text-hint bg-hint/15 border-hint/40",
  escape: "text-hint bg-hint/15 border-hint/40",
  self_correction: "text-solved bg-solved/15 border-solved/50 ring-1 ring-solved/30",
  summary: "text-accent bg-accent-soft border-accent/40",
};

function buildEvents(trace: ThinkingTrace): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  trace.subproblems.forEach((sp, i) => {
    const hints = typeof sp.hints_used === "number" ? sp.hints_used : 0;
    events.push({
      kind: "solved",
      caption: sp.description,
      meta: `${sp.id} · ${hints} hint${hints !== 1 ? "s" : ""}`,
    });
    if (sp.escape_hatch_reflection) {
      events.push({
        kind: "escape",
        caption: `Asked for the answer on ${sp.id}. Noted: "${sp.escape_hatch_reflection}"`,
      });
    }
    void i;
  });

  const corrections =
    typeof trace.self_corrections === "number" ? trace.self_corrections : 0;
  if (corrections > 0) {
    events.push({
      kind: "self_correction",
      caption: `Changed your mind ${corrections} time${
        corrections !== 1 ? "s" : ""
      } — and caught yourself doing it.`,
      highlight: true,
    });
  }

  return events;
}

export function TraceTimeline({ trace }: { trace: ThinkingTrace }) {
  const events = buildEvents(trace);
  if (events.length === 0) return null;

  return (
    <section className="space-y-3">
      <h3 className="font-display text-xl font-semibold text-ink">
        How it unfolded
      </h3>
      <ol className="relative space-y-3 before:absolute before:top-3 before:bottom-3 before:left-[11px] before:w-px before:bg-rule">
        {events.map((e, i) => (
          <TimelineRow key={i} event={e} index={i} />
        ))}
      </ol>
    </section>
  );
}

function TimelineRow({ event, index }: { event: TimelineEvent; index: number }) {
  const ref = useRef<HTMLLIElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10%" });
  const Icon = ICONS[event.kind];
  const tone = TONES[event.kind];

  return (
    <motion.li
      ref={ref}
      initial={{ opacity: 0, x: -8 }}
      animate={inView ? { opacity: 1, x: 0 } : { opacity: 0, x: -8 }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
      className="relative flex gap-4 items-start pl-0"
    >
      <span
        className={`relative z-10 mt-0.5 inline-flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border bg-paper ${tone} ${
          event.highlight ? "shadow-[0_0_0_3px_rgb(var(--color-solved)/0.15)]" : ""
        }`}
      >
        <Icon size={12} strokeWidth={2} />
      </span>
      <div className="flex-1 min-w-0 pb-1">
        <p className="text-body text-ink leading-snug">
          <MathText inline>{event.caption}</MathText>
        </p>
        {event.meta && (
          <p className="font-mono text-mono text-ink-faint mt-0.5">{event.meta}</p>
        )}
      </div>
    </motion.li>
  );
}
