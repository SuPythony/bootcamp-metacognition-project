import { useEffect, useState } from "react";
import type { ThinkingTrace } from "../api/types";
import { api } from "../api/client";
import ThinkingTraceDrawer from "../components/ThinkingTraceDrawer";

export default function WrapUpView({
  sessionId,
  onRestart,
}: {
  sessionId: string;
  onRestart: () => void;
}) {
  const [trace, setTrace] = useState<ThinkingTrace | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api
      .thinkingTrace(sessionId)
      .then(setTrace)
      .catch(() => setTrace(null))
      .finally(() => setIsLoading(false));
  }, [sessionId]);

  return (
    <main
      data-testid="wrap-up-view"
      className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-white p-6"
    >
      <div className="max-w-xl mx-auto space-y-6">
        <div className="text-center space-y-1.5">
          <h1 className="text-2xl font-bold text-indigo-900">Session complete</h1>
          <p className="text-gray-500 text-sm">
            Here's how your thinking developed.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-sm text-gray-400">
            Loading your thinking trace…
          </div>
        ) : trace ? (
          <ThinkingTraceDrawer trace={trace} />
        ) : (
          <div className="flex items-center justify-center py-16 text-sm text-gray-400">
            Could not load thinking trace.
          </div>
        )}

        <button
          onClick={onRestart}
          className="w-full py-3 bg-indigo-600 text-white rounded-xl font-semibold text-sm hover:bg-indigo-700 active:bg-indigo-800 transition-colors"
        >
          Start a new session
        </button>
      </div>
    </main>
  );
}
