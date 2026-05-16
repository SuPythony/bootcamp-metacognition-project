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
    <div data-testid="algebra-steps" className="text-body">
      <ol className="space-y-2 list-none">
        {steps.map((s, i) => (
          <li key={i} className="grid grid-cols-[20px_1fr_auto] items-baseline gap-3">
            <span className="font-mono text-mono text-ink-faint text-right">
              {i + 1}.
            </span>
            <span className="text-ink">
              <MathText inline>{`$${s.expr}$`}</MathText>
            </span>
            <span className="font-display text-caption italic text-ink-soft shrink-0">
              {s.rule}
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-3 pt-3 border-t border-rule grid grid-cols-[20px_1fr_auto] items-baseline gap-3">
        <span className="font-mono text-mono text-accent text-right">∴</span>
        <span className="text-body-emphasis text-ink">
          <MathText inline>{`$${final}$`}</MathText>
        </span>
        <span className="text-label text-accent">final</span>
      </div>
    </div>
  );
}
