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
    <div data-testid="algebra-steps">
      <ol>
        {steps.map((s, i) => (
          <li key={i}>
            <code>{s.expr}</code> — {s.rule}
          </li>
        ))}
      </ol>
      <div>= {final}</div>
    </div>
  );
}
