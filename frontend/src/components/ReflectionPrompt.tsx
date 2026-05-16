import { motion } from "framer-motion";
import { Eye } from "lucide-react";
import MathText from "./MathText";

const TRIGGER_LABEL: Record<string, string> = {
  periodic: "Pause and reflect",
  self_correction: "You just changed your mind",
  escape_hatch: "Before I show you",
  wrap_up: "Looking back",
};

export default function ReflectionPrompt({
  question,
  trigger = "periodic",
}: {
  question: string;
  trigger?: "periodic" | "self_correction" | "escape_hatch" | "wrap_up";
  // onSelect is passed by ChatPane but not used here — the student answers
  // in the main chat input; the backend attaches it via pending_reflection_index
  onSelect?: (value: unknown) => void;
}) {
  const label = TRIGGER_LABEL[trigger] ?? "Reflect";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      data-testid="reflection-prompt"
      className="bg-surface border border-rule rounded-md p-5 relative overflow-hidden shadow-sm"
    >
      <span
        className="absolute left-0 top-0 bottom-0 w-1.5 bg-hint"
        aria-hidden
      />
      <div className="pl-4 space-y-3">
        <div className="flex items-center gap-2">
          <Eye size={14} className="text-hint" strokeWidth={1.8} />
          <p className="text-label text-hint">{label}</p>
        </div>
        <p className="font-display text-serif-lede italic text-ink leading-snug">
          <MathText inline>{question}</MathText>
        </p>
        <p className="text-caption text-ink-faint flex items-center gap-1.5">
          <span className="inline-block w-3 h-px bg-rule" aria-hidden />
          Type your answer in the chat below
        </p>
      </div>
    </motion.div>
  );
}
