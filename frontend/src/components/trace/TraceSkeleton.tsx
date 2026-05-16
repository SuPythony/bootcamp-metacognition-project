function Bar({ className }: { className?: string }) {
  return (
    <span
      className={`block bg-surface-muted rounded-md animate-pulse ${className ?? ""}`}
      aria-hidden
    />
  );
}

export default function TraceSkeleton() {
  return (
    <div
      data-testid="trace-skeleton"
      role="status"
      aria-label="Loading your thinking trace"
      className="space-y-10"
    >
      <section className="space-y-4">
        <Bar className="h-3 w-32" />
        <Bar className="h-10 w-3/4" />
        <Bar className="h-px w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Bar className="h-28 w-full" />
          <Bar className="h-28 w-full" />
        </div>
      </section>

      <section className="space-y-3">
        <Bar className="h-5 w-40" />
        <div className="space-y-2 pl-6">
          <Bar className="h-6 w-3/4" />
          <Bar className="h-6 w-2/3" />
          <Bar className="h-6 w-1/2" />
        </div>
      </section>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-6 border-t border-b border-rule py-5">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <Bar className="h-10 w-12" />
            <Bar className="h-3 w-20" />
          </div>
        ))}
      </section>
    </div>
  );
}
