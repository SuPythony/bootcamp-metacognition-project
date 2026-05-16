import { useEffect, useRef, useState } from "react";
import type { Domain } from "../api/types";
import { api } from "../api/client";

type Step = "username" | "query";

export default function OnboardingView({
  onSessionStart,
  onPersonaSession,
  initialStep = "username",
  initialUsername = "",
}: {
  onSessionStart: (sessionId: string, openingMessage: string, domain: Domain) => void;
  onPersonaSession?: (sessionId: string, openingMessage: string, username: string) => void;
  initialStep?: Step;
  initialUsername?: string;
}) {
  const [step, setStep] = useState<Step>(initialStep);
  const [username, setUsername] = useState(initialUsername);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmNew, setConfirmNew] = useState(false);

  const usernameRef = useRef<HTMLInputElement>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (step === "username") usernameRef.current?.focus();
    else queryRef.current?.focus();
  }, [step]);

  async function handleUsername(e: React.FormEvent) {
    e.preventDefault();
    const user = username.trim();
    if (!user) return;

    if (confirmNew) {
      // User confirmed — create the persona
      setIsLoading(true);
      setError(null);
      try {
        const res = await api.personaCreate(user, { confirm: true });
        if (res.status === "pending" && res.session_id && res.opening_message) {
          onPersonaSession?.(res.session_id, res.opening_message, user);
          return;
        }
        // Shouldn't happen with confirm=true, but handle gracefully
        setStep("query");
      } catch {
        setError("Could not connect. Is the backend running?");
      } finally {
        setIsLoading(false);
      }
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await api.personaCreate(user);
      if (res.status === "exists") {
        setStep("query");
      } else if (res.status === "confirm_new") {
        setConfirmNew(true);
      } else if (res.status === "pending" && res.session_id && res.opening_message) {
        onPersonaSession?.(res.session_id, res.opening_message, user);
      }
    } catch {
      setError("Could not connect. Is the backend running?");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleQuery(e: React.FormEvent) {
    e.preventDefault();
    const user = username.trim();
    const q = query.trim();
    if (!user || !q) return;

    setIsLoading(true);
    setError(null);
    try {
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
          <h1 className="text-3xl font-bold text-indigo-900 tracking-tight">Socratic Tutor</h1>
          <p className="text-gray-500 text-sm">
            Bring a problem. Work through it yourself — I'll guide, not tell.
          </p>
        </div>

        {step === "username" ? (
          <form
            onSubmit={handleUsername}
            className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4"
          >
            <div className="space-y-1.5">
              <label htmlFor="username" className="text-sm font-medium text-gray-700">
                What's your name?
              </label>
              <input
                id="username"
                ref={usernameRef}
                type="text"
                placeholder="e.g. alex"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  setConfirmNew(false);
                  setError(null);
                }}
                className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                disabled={isLoading}
                autoComplete="off"
              />
            </div>

            {confirmNew && (
              <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 space-y-2 text-sm">
                <p className="text-amber-800">
                  We don't recognise <strong>{username.trim()}</strong>. Start fresh?
                </p>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold disabled:opacity-40 hover:bg-indigo-700"
                  >
                    {isLoading ? "Creating…" : "Yes, create new account"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmNew(false);
                      setUsername("");
                      setError(null);
                      usernameRef.current?.focus();
                    }}
                    className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-semibold hover:bg-gray-200"
                  >
                    No, try again
                  </button>
                </div>
              </div>
            )}

            {error && <p className="text-sm text-red-600">{error}</p>}

            {!confirmNew && (
              <button
                type="submit"
                disabled={isLoading || !username.trim()}
                className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700 active:bg-indigo-800 transition-colors"
              >
                {isLoading ? "Checking…" : "Continue"}
              </button>
            )}
          </form>
        ) : (
          <form
            onSubmit={handleQuery}
            className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4"
          >
            <p className="text-base font-medium text-gray-800">
              Welcome back, {username.trim()}!
            </p>
            <div className="space-y-1.5">
              <label htmlFor="query" className="text-sm font-medium text-gray-700">
                What would you like to work on today?
              </label>
              <textarea
                id="query"
                ref={queryRef}
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
              disabled={isLoading || !query.trim()}
              className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700 active:bg-indigo-800 transition-colors"
            >
              {isLoading ? "Starting…" : "Start learning"}
            </button>

            <button
              type="button"
              onClick={() => {
                setStep("username");
                setUsername("");
                setConfirmNew(false);
                setError(null);
              }}
              className="w-full text-xs text-gray-400 hover:text-gray-600"
            >
              ← Not {username.trim()}?
            </button>
          </form>
        )}

        <p className="text-center text-xs text-gray-400">
          No account needed — your progress is saved by username.
        </p>
      </div>
    </main>
  );
}
