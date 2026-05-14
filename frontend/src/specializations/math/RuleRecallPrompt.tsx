// Inline Socratic widget — asks which rule applies. Props must NOT include the
// correct answer (enforced on the backend in the Socratic base prompt).

export default function RuleRecallPrompt({
  candidate_rules,
  context_expr,
}: {
  candidate_rules: string[];
  context_expr: string;
}) {
  return (
    <div data-testid="rule-recall-prompt">
      <p>
        Which rule applies to <code>{context_expr}</code>?
      </p>
      <ul>
        {candidate_rules.map((r) => (
          <li key={r}>
            <button>{r}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
