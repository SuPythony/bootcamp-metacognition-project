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
    <div
      data-testid="reflection-prompt"
      className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm"
    >
      <p className="text-[11px] font-semibold text-amber-600 uppercase tracking-wide mb-1.5">
        {label}
      </p>
      <p className="text-amber-900 leading-snug">
        <MathText inline>{question}</MathText>
      </p>
      <p className="text-xs text-amber-500 mt-2 italic">
        Type your answer in the chat below
      </p>
    </div>
  );
}
