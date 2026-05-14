export default function HintBadge({ count }: { count: number }) {
  return <span data-testid="hint-badge">{count}</span>;
}
