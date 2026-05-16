import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import type { Domain } from "../api/types";
import { api } from "../api/client";
import { Brandmark } from "../components/brand/Brandmark";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import ErrorCard from "../components/ErrorCard";

const RULED_BG =
  "repeating-linear-gradient(to bottom, transparent 0, transparent 31px, rgb(var(--color-rule)) 31px, rgb(var(--color-rule)) 32px)";

export default function OnboardingView({
  onSessionStart,
}: {
  onSessionStart: (
    sessionId: string,
    openingMessage: string,
    domain: Domain,
    originalQuery: string,
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
      onSessionStart(session.session_id, session.opening_message, session.domain, q);
    } catch {
      setError("Could not connect. Is the backend running?");
      setIsLoading(false);
    }
  }

  return (
    <main
      data-testid="onboarding-view"
      className="min-h-screen bg-paper flex flex-col"
    >
      <header className="flex items-center justify-between px-6 py-5">
        <Brandmark wordmark />
        <ThemeToggle />
      </header>

      <div className="flex-1 flex items-start justify-center px-6 pt-12 pb-20">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-2xl space-y-12"
        >
          <div className="space-y-4">
            <h1 className="font-display text-display font-semibold text-ink leading-[1.05]">
              What're you working on today?
            </h1>
            <p className="font-display text-serif-lede italic text-ink-soft max-w-md">
              Bring a problem. Loom won't solve it — it'll help you solve it yourself.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-10">
            <div className="space-y-1.5">
              <label htmlFor="username" className="text-label text-ink-faint block">
                Call me
              </label>
              <input
                id="username"
                type="text"
                placeholder="your name"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-transparent border-0 border-b border-rule px-0 py-2 text-body text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none transition-colors"
                disabled={isLoading}
                autoFocus
                autoComplete="off"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="query" className="text-label text-ink-faint block">
                The problem
              </label>
              <div className="relative">
                <span
                  className="absolute left-0 top-0 bottom-0 w-px bg-alarm/30"
                  aria-hidden
                />
                <textarea
                  id="query"
                  placeholder="e.g. How do I solve 2x + 3 = 7?"
                  rows={5}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="relative w-full bg-transparent pl-6 pr-2 py-1 text-body text-ink placeholder:text-ink-faint focus:outline-none resize-none"
                  style={{
                    backgroundImage: RULED_BG,
                    backgroundPosition: "0 7px",
                    lineHeight: "32px",
                  }}
                  disabled={isLoading}
                />
              </div>
            </div>

            {error && (
              <ErrorCard
                title="Can't reach the tutor"
                message={error}
                onRetry={() => setError(null)}
                retryLabel="Dismiss"
              />
            )}

            <button
              type="submit"
              disabled={isLoading || !username.trim() || !query.trim()}
              className="w-full inline-flex items-center justify-center gap-2 py-3 bg-accent text-white rounded-md text-body-emphasis disabled:opacity-40 hover:opacity-90 active:scale-[0.99] transition-all"
            >
              {isLoading ? "Starting…" : "Begin"}
              {!isLoading && <ArrowRight size={16} strokeWidth={1.8} />}
            </button>
          </form>
        </motion.div>
      </div>
    </main>
  );
}
