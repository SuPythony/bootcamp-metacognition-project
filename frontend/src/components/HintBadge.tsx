export default function HintBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span
      data-testid="hint-badge"
      className="inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold bg-amber-100 text-amber-700 rounded-full"
    >
      {count}
    </span>
  );
}
