import { RefreshCw } from "lucide-react";

interface ErrorCardProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export default function ErrorCard({
  title = "Something went off course",
  message,
  onRetry,
  retryLabel = "Try again",
}: ErrorCardProps) {
  return (
    <div
      role="alert"
      className="bg-surface border border-rule rounded-md p-5 max-w-md mx-auto space-y-4"
    >
      <div className="flex items-start gap-3">
        <svg
          viewBox="0 0 32 32"
          className="w-10 h-10 text-alarm shrink-0"
          aria-hidden
        >
          <circle
            cx="16"
            cy="16"
            r="13"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeDasharray="3 2"
          />
          <path
            d="M16 9 L16 17"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <circle cx="16" cy="21.5" r="1.2" fill="currentColor" />
        </svg>
        <div className="space-y-1.5 min-w-0">
          <p className="font-display text-serif-lede font-semibold text-ink">
            {title}
          </p>
          <p className="text-body text-ink-soft break-words">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 text-body-emphasis text-accent hover:underline"
        >
          <RefreshCw size={14} strokeWidth={1.8} />
          {retryLabel}
        </button>
      )}
    </div>
  );
}
