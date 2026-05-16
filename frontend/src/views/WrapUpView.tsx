import { useEffect, useState } from "react";
import type { ThinkingTrace } from "../api/types";
import { api } from "../api/client";
import ThinkingTraceDrawer from "../components/ThinkingTraceDrawer";
import ErrorCard from "../components/ErrorCard";
import TraceSkeleton from "../components/trace/TraceSkeleton";
import { Brandmark } from "../components/brand/Brandmark";
import { ThemeToggle } from "../components/theme/ThemeToggle";

export default function WrapUpView({
  sessionId,
  onRestart,
}: {
  sessionId: string;
  onRestart: () => void;
}) {
  const [trace, setTrace] = useState<ThinkingTrace | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    api
      .thinkingTrace(sessionId)
      .then(setTrace)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load trace."))
      .finally(() => setIsLoading(false));
  }

  useEffect(load, [sessionId]);

  return (
    <main data-testid="wrap-up-view" className="min-h-screen bg-paper">
      <header className="flex items-center justify-between px-6 py-5">
        <Brandmark wordmark />
        <ThemeToggle />
      </header>

      <div className="max-w-3xl mx-auto px-6 pb-16 space-y-10">
        {isLoading ? (
          <TraceSkeleton />
        ) : error ? (
          <ErrorCard
            title="Couldn't pull your trace"
            message={error}
            onRetry={load}
          />
        ) : trace ? (
          <ThinkingTraceDrawer trace={trace} />
        ) : (
          <ErrorCard
            title="Trace empty"
            message="No thinking trace returned for this session."
            onRetry={load}
          />
        )}

        {!isLoading && trace && (
          <button
            onClick={onRestart}
            className="w-full py-3 bg-accent text-white rounded-md text-body-emphasis hover:opacity-90 active:scale-[0.99] transition-all"
          >
            Start a new session
          </button>
        )}
      </div>
    </main>
  );
}
