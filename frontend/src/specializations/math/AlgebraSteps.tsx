import MathText from "../../components/MathText";

interface Step {
  expr: string;
  rule: string;
}

export default function AlgebraSteps({
  steps,
  final,
}: {
  steps: Step[];
  final: string;
}) {
  return (
    <div data-testid="algebra-steps" className="text-sm space-y-1.5">
      <ol className="space-y-1.5 list-none">
        {steps.map((s, i) => (
          <li key={i} className="flex items-baseline gap-2">
            <span className="shrink-0 text-gray-400 text-xs w-4 text-right">
              {i + 1}.
            </span>
            <span className="flex-1">
              <MathText inline>{`$${s.expr}$`}</MathText>
            </span>
            <span className="text-xs text-gray-500 italic shrink-0">{s.rule}</span>
          </li>
        ))}
      </ol>
      <div className="mt-2 pt-2 border-t border-gray-200 font-semibold">
        <MathText inline>{`$${final}$`}</MathText>
      </div>
    </div>
  );
}
