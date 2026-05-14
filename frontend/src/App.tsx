import { useState, Component } from "react";
import type { ReactNode } from "react";
import type { Domain } from "./api/types";
import OnboardingView from "./views/OnboardingView";
import SessionView from "./views/SessionView";
import WrapUpView from "./views/WrapUpView";

class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null };
  static getDerivedStateFromError(e: Error) { return { error: e.message }; }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-white p-8">
          <div className="max-w-md space-y-3 text-center">
            <p className="text-red-600 font-semibold">Something crashed</p>
            <p className="text-sm text-gray-500 font-mono break-all">{this.state.error}</p>
            <button
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

type Route =
  | { kind: "onboarding" }
  | { kind: "session"; sessionId: string; domain: Domain; openingMessage: string }
  | { kind: "wrap_up"; sessionId: string };

export default function App() {
  const [route, setRoute] = useState<Route>({ kind: "onboarding" });

  switch (route.kind) {
    case "onboarding":
      return (
        <ErrorBoundary>
          <OnboardingView
            onSessionStart={(sessionId, openingMessage, domain) =>
              setRoute({ kind: "session", sessionId, domain, openingMessage })
            }
          />
        </ErrorBoundary>
      );
    case "session":
      return (
        <ErrorBoundary>
          <SessionView
            sessionId={route.sessionId}
            domain={route.domain}
            openingMessage={route.openingMessage}
            onWrapUp={() =>
              setRoute({ kind: "wrap_up", sessionId: route.sessionId })
            }
          />
        </ErrorBoundary>
      );
    case "wrap_up":
      return (
        <ErrorBoundary>
          <WrapUpView
            sessionId={route.sessionId}
            onRestart={() => setRoute({ kind: "onboarding" })}
          />
        </ErrorBoundary>
      );
  }
}
