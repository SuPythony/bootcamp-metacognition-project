import { useState } from "react";

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

  function handlePick(n: number) {
    if (selected !== null) return;
    setSelected(n);
    onSelect?.(n);
  }

  return (
    <div
      data-testid="calibration-check"
      className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm"
    >
      <p className="text-[11px] font-semibold text-blue-500 uppercase tracking-wide mb-1.5">
        Confidence check
      </p>
      <p className="text-gray-700 mb-3">{question}</p>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => handlePick(n)}
            disabled={selected !== null}
            title={LABELS[n]}
            className={`
              w-9 h-9 rounded-lg text-sm font-semibold border transition-colors
              ${
                selected === n
                  ? "bg-blue-600 text-white border-blue-600"
                  : selected !== null
                  ? "bg-gray-100 text-gray-400 border-gray-200 cursor-default"
                  : "bg-white text-blue-700 border-blue-300 hover:bg-blue-100"
              }
            `}
          >
            {n}
          </button>
        ))}
      </div>
      {selected !== null && (
        <p className="text-xs text-blue-600 mt-2 italic">
          Got it — {LABELS[selected].toLowerCase()}. We'll compare after you try.
        </p>
      )}
    </div>
  );
}
