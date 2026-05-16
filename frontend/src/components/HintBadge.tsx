export default function HintBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span
      data-testid="hint-badge"
      className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-semibold bg-hint/15 text-hint rounded-full"
      aria-label={`${count} hint${count !== 1 ? "s" : ""} used`}
    >
      {count}
    </span>
  );
}
