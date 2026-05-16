export function HandDrawnRule({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 400 8"
      preserveAspectRatio="none"
      role="presentation"
      aria-hidden
      className={`block w-full h-2 text-rule ${className ?? ""}`}
    >
      <path
        d="M2 4 Q 60 1, 120 4 T 240 4 T 360 4 T 398 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}
