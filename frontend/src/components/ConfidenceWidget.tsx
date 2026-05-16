import { useState } from "react";

const LABELS: Record<number, string> = {
  1: "Very unsure",
  2: "Unsure",
  3: "Okay",
  4: "Fairly confident",
  5: "Very confident",
};

export default function ConfidenceWidget({
  onSelect,
}: {
  onSelect: (value: 1 | 2 | 3 | 4 | 5) => void;
}) {
  const [selected, setSelected] = useState<1 | 2 | 3 | 4 | 5 | null>(null);

  function handlePick(n: 1 | 2 | 3 | 4 | 5) {
    if (selected !== null) return;
    setSelected(n);
    onSelect(n);
  }

  return (
    <div data-testid="confidence-widget" className="space-y-2.5">
      <p className="text-body-emphasis text-ink">
        How confident are you in this solution?
      </p>
      <div className="flex gap-2">
        {([1, 2, 3, 4, 5] as const).map((n) => {
          const active = selected === n;
          const locked = selected !== null;
          return (
            <button
              key={n}
              onClick={() => handlePick(n)}
              disabled={locked}
              aria-label={LABELS[n]}
              aria-pressed={active}
              className={`flex flex-col items-center gap-1 px-3 py-2 border rounded-md transition-colors ${
                active
                  ? "border-accent bg-accent text-white"
                  : locked
                  ? "border-rule bg-surface-muted text-ink-faint cursor-default"
                  : "border-rule bg-paper text-ink hover:border-accent hover:bg-accent-soft"
              }`}
            >
              <span className="text-body-emphasis">{n}</span>
              <span
                className={`text-[10px] w-14 text-center leading-tight ${
                  active ? "text-white/80" : "text-ink-faint"
                }`}
              >
                {LABELS[n]}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
