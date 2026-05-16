import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import type { ThinkingTrace } from "../../api/types";
import MathText from "../MathText";
import { Brandmark } from "../brand/Brandmark";
import { HandDrawnRule } from "./HandDrawnRule";

const DELTA_TEXT: Record<ThinkingTrace["understanding_delta_label"], string> = {
  significant: "significant shift",
  moderate: "moderate shift",
  small: "small shift",
};

const DELTA_TONE: Record<ThinkingTrace["understanding_delta_label"], string> = {
  significant: "text-solved border-solved/40 bg-solved/10",
  moderate: "text-hint border-hint/40 bg-hint/10",
  small: "text-ink-soft border-rule bg-surface-muted",
};

interface TraceHeroProps {
  trace: ThinkingTrace;
  domain?: string;
  dateISO?: string;
}

export function TraceHero({ trace, domain, dateISO }: TraceHeroProps) {
  const date = dateISO ?? new Date().toISOString().slice(0, 10);

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <Brandmark size={28} />
          <p className="text-label text-ink-faint">
            {date}
            {domain ? ` · ${domain}` : ""}
          </p>
        </div>
        <h2 className="font-display text-display font-semibold text-ink leading-[1.05]">
          Your thinking, traced.
        </h2>
        <HandDrawnRule />
      </div>

      <Diptych trace={trace} />
    </section>
  );
}

function Diptych({ trace }: { trace: ThinkingTrace }) {
  const hasInitial = Boolean(trace.initial_understanding);
  const hasFinal = Boolean(trace.final_understanding);
  if (!hasInitial && !hasFinal) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 md:gap-5 items-stretch">
        {hasInitial && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="bg-surface border border-rule rounded-md p-5 space-y-2"
          >
            <p className="text-label text-ink-faint">I started thinking…</p>
            <p className="font-display italic text-serif-lede text-ink-soft leading-snug">
              "<MathText inline>{trace.initial_understanding}</MathText>"
            </p>
          </motion.div>
        )}

        {hasInitial && hasFinal && (
          <div className="hidden md:flex flex-col items-center justify-center gap-2 px-1">
            <ArrowRight
              size={20}
              strokeWidth={1.4}
              className="text-ink-faint"
              aria-hidden
            />
            <DeltaChip label={trace.understanding_delta_label} />
          </div>
        )}

        {hasFinal && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
            className="bg-accent-soft border border-accent/30 rounded-md p-5 space-y-2"
          >
            <p className="text-label text-accent">I ended up here.</p>
            <p className="text-body-emphasis text-ink leading-snug">
              "<MathText inline>{trace.final_understanding}</MathText>"
            </p>
          </motion.div>
        )}
      </div>

      {hasInitial && hasFinal && (
        <div className="md:hidden flex justify-center">
          <DeltaChip label={trace.understanding_delta_label} />
        </div>
      )}

      {trace.understanding_delta_evidence && (
        <p className="text-caption text-ink-soft italic">
          <MathText inline>{trace.understanding_delta_evidence}</MathText>
        </p>
      )}
    </div>
  );
}

function DeltaChip({ label }: { label: ThinkingTrace["understanding_delta_label"] }) {
  // Backend may return null/unknown labels on summariser failure. Skip the
  // chip rather than render an "undefined" classname.
  if (!label || !(label in DELTA_TEXT)) return null;
  return (
    <motion.span
      initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className={`text-label px-2.5 py-1 rounded-full border whitespace-nowrap ${DELTA_TONE[label]}`}
    >
      {DELTA_TEXT[label]}
    </motion.span>
  );
}
