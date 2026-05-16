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
  return (
    <div data-testid="confidence-widget" className="space-y-2.5">
      <p className="text-body-emphasis text-ink">
        How confident are you in this solution?
      </p>
      <div className="flex gap-2">
        {([1, 2, 3, 4, 5] as const).map((n) => (
          <button
            key={n}
            onClick={() => onSelect(n)}
            aria-label={LABELS[n]}
            className="flex flex-col items-center gap-1 px-3 py-2 border border-rule bg-paper rounded-md hover:border-accent hover:bg-accent-soft transition-colors"
          >
            <span className="text-body-emphasis text-ink">{n}</span>
            <span className="text-[10px] text-ink-faint w-14 text-center leading-tight">
              {LABELS[n]}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
