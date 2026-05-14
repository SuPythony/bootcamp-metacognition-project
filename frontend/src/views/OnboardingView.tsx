import { useState } from "react";
import type { Domain } from "../api/types";
import { api } from "../api/client";

export default function OnboardingView({
  onSessionStart,
}: {
  onSessionStart: (
    sessionId: string,
    openingMessage: string,
    domain: Domain
  ) => void;
}) {
  const [username, setUsername] = useState("");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const user = username.trim();
    const q = query.trim();
    if (!user || !q) return;

    setIsLoading(true);
    setError(null);
    try {
      await api.personaCreate(user);
      const session = await api.sessionNew({ username: user, query: q, mode: "solving" });
      onSessionStart(session.session_id, session.opening_message, session.domain);
    } catch {
      setError("Could not connect. Is the backend running?");
      setIsLoading(false);
    }
  }

  return (
    <main
      data-testid="onboarding-view"
      className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-white flex items-center justify-center p-6"
    >
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-indigo-900 tracking-tight">
            Socratic Tutor
          </h1>
          <p className="text-gray-500 text-sm">
            Bring a problem. Work through it yourself — I'll guide, not tell.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4"
        >
          <div className="space-y-1.5">
            <label
              htmlFor="username"
              className="text-sm font-medium text-gray-700"
            >
              Your name
            </label>
            <input
              id="username"
              type="text"
              placeholder="e.g. alex"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              disabled={isLoading}
              autoFocus
              autoComplete="off"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="query"
              className="text-sm font-medium text-gray-700"
            >
              What problem do you want to work through?
            </label>
            <textarea
              id="query"
              placeholder="e.g. How do I solve 2x + 3 = 7?"
              rows={3}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              disabled={isLoading}
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isLoading || !username.trim() || !query.trim()}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700 active:bg-indigo-800 transition-colors"
          >
            {isLoading ? "Starting…" : "Start learning"}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400">
          No account needed — your progress is saved by username.
        </p>
      </div>
    </main>
  );
}
