import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Compass } from "lucide-react";

const LABELS: Record<number, string> = {
  1: "Not sure at all",
  2: "Slightly sure",
  3: "Somewhat sure",
  4: "Fairly confident",
  5: "Very confident",
};

export default function CalibrationCheck({
  question = "Before you try — how confident are you that you'll get this right?",
  onSelect,
}: {
  question?: string;
  onSelect?: (value: number) => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);

  function handlePick(n: number) {
    if (selected !== null) return;
    setSelected(n);
    onSelect?.(n);
  }

  function handleKey(e: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    if (selected !== null) return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      buttonsRef.current[(index + 1) % 5]?.focus();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      buttonsRef.current[(index + 4) % 5]?.focus();
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      data-testid="calibration-check"
      className="bg-surface border border-rule rounded-md p-4 relative overflow-hidden"
    >
      <span
        className="absolute left-0 top-0 bottom-0 w-1 bg-calibrate"
        aria-hidden
      />
      <div className="pl-3 space-y-3">
        <div className="flex items-center gap-2">
          <Compass size={14} className="text-calibrate" strokeWidth={1.8} />
          <p className="text-label text-calibrate">Confidence check</p>
        </div>
        <p className="font-display text-serif-lede text-ink italic leading-snug">
          {question}
        </p>

        <div
          role="radiogroup"
          aria-label="Confidence level"
          className="flex items-stretch rounded-md border border-rule overflow-hidden bg-paper"
        >
          {[1, 2, 3, 4, 5].map((n, i) => {
            const active = selected === n;
            const isLocked = selected !== null;
            return (
              <button
                key={n}
                ref={(el) => {
                  buttonsRef.current[i] = el;
                }}
                role="radio"
                aria-checked={active}
                aria-label={LABELS[n]}
                onClick={() => handlePick(n)}
                onKeyDown={(e) => handleKey(e, i)}
                disabled={isLocked}
                tabIndex={selected === null ? (i === 0 ? 0 : -1) : -1}
                title={LABELS[n]}
                className={`relative flex-1 py-2.5 text-body-emphasis transition-colors border-r border-rule last:border-r-0 ${
                  active
                    ? "bg-calibrate text-white"
                    : isLocked
                    ? "text-ink-faint cursor-default"
                    : "text-calibrate hover:bg-calibrate/10"
                }`}
              >
                {n}
                {active && (
                  <motion.span
                    layoutId="calibration-marker"
                    className="absolute inset-x-2 -bottom-px h-0.5 bg-paper"
                  />
                )}
              </button>
            );
          })}
        </div>
        <div className="flex justify-between text-caption text-ink-faint">
          <span>Not sure</span>
          <span>Very confident</span>
        </div>

        {selected !== null && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
            className="text-caption text-calibrate italic"
          >
            Got it — {LABELS[selected].toLowerCase()}. We'll compare after you try.
          </motion.p>
        )}
      </div>
    </motion.div>
  );
}
