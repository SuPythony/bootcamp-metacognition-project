export default function ConfidenceWidget({
  onSelect,
}: {
  onSelect: (value: 1 | 2 | 3 | 4 | 5) => void;
}) {
  return (
    <div data-testid="confidence-widget">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} onClick={() => onSelect(n as 1 | 2 | 3 | 4 | 5)}>
          {n}
        </button>
      ))}
    </div>
  );
}
