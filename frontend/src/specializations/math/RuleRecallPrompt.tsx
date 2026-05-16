// Inline Socratic widget — asks which rule applies. Props must NOT include the
// correct answer (enforced on the backend in the Socratic base prompt).
import { useState } from "react";
import { motion } from "framer-motion";
import { Scale } from "lucide-react";
import MathText from "../../components/MathText";

export default function RuleRecallPrompt({
  candidate_rules,
  context_expr,
  onSelect,
}: {
  candidate_rules: string[];
  context_expr: string;
  onSelect?: (value: string) => void;
}) {
  const [picked, setPicked] = useState<string | null>(null);

  function handlePick(r: string) {
    if (picked !== null) return;
    setPicked(r);
    onSelect?.(r);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      data-testid="rule-recall-prompt"
      className="bg-surface border border-rule rounded-md p-4 relative overflow-hidden"
    >
      <span
        className="absolute left-0 top-0 bottom-0 w-1 bg-accent"
        aria-hidden
      />
      <div className="pl-3 space-y-3">
        <div className="flex items-center gap-2">
          <Scale size={14} className="text-accent" strokeWidth={1.8} />
          <p className="text-label text-accent">Rule recall</p>
        </div>
        <p className="font-display text-serif-lede italic text-ink leading-snug">
          Which rule applies to{" "}
          <span className="inline-block font-mono not-italic bg-surface-muted text-ink rounded px-1.5 py-0.5 text-mono">
            <MathText inline>{context_expr}</MathText>
          </span>
          ?
        </p>
        <div className="flex flex-wrap gap-2">
          {candidate_rules.map((r) => {
            const active = picked === r;
            const locked = picked !== null;
            return (
              <button
                key={r}
                onClick={() => handlePick(r)}
                disabled={locked}
                className={`px-3 py-1.5 rounded-md border text-body-emphasis transition-colors ${
                  active
                    ? "bg-accent text-white border-accent"
                    : locked
                    ? "bg-surface-muted text-ink-faint border-rule cursor-default"
                    : "bg-paper text-ink border-rule hover:border-accent hover:bg-accent-soft"
                }`}
              >
                <MathText inline>{r}</MathText>
              </button>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
