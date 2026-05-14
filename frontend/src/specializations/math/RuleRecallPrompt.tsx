// Inline Socratic widget — asks which rule applies. Props must NOT include the
// correct answer (enforced on the backend in the Socratic base prompt).
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
  return (
    <div
      data-testid="rule-recall-prompt"
      className="bg-white border border-indigo-200 rounded-xl p-3 text-sm shadow-sm"
    >
      <p className="text-gray-700 mb-2 font-medium">
        Which rule applies to{" "}
        <span className="inline-block bg-gray-100 rounded px-1.5 py-0.5">
          <MathText inline>{context_expr}</MathText>
        </span>
        ?
      </p>
      <div className="flex flex-wrap gap-2">
        {candidate_rules.map((r) => (
          <button
            key={r}
            onClick={() => onSelect?.(r)}
            className="px-3 py-1.5 rounded-lg border border-indigo-300 bg-indigo-50 hover:bg-indigo-100 text-indigo-800 transition-colors text-sm"
          >
            <MathText inline>{r}</MathText>
          </button>
        ))}
      </div>
    </div>
  );
}
