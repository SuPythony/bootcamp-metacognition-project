import type { CSSProperties } from "react";

interface BrandmarkProps {
  size?: number;
  wordmark?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function Brandmark({ size = 28, wordmark = false, className, style }: BrandmarkProps) {
  return (
    <div className={`flex items-center gap-2 ${className ?? ""}`} style={style}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        role="img"
        aria-label="Aporeka"
        className="text-accent"
      >
        <rect x="0.5" y="0.5" width="27" height="27" rx="6" className="fill-accent-soft" />
        <path
          d="M7 7 L7 21 M14 7 L14 21 M21 7 L21 21"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          fill="none"
        />
        <path
          d="M5 11 Q14 14 23 11 M5 17 Q14 20 23 17"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          fill="none"
          opacity="0.65"
        />
      </svg>
      {wordmark && (
        <span className="font-display text-[1.25rem] font-semibold tracking-tight text-ink">
          Aporeka
        </span>
      )}
    </div>
  );
}
