import { useState, Component } from "react";
import type { ReactNode } from "react";
import type { Domain } from "./api/types";
import OnboardingView from "./views/OnboardingView";
import SessionView from "./views/SessionView";
import WrapUpView from "./views/WrapUpView";
import ErrorCard from "./components/ErrorCard";

class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null };
  static getDerivedStateFromError(e: Error) { return { error: e.message }; }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-paper p-8">
          <ErrorCard
            title="Something crashed"
            message={this.state.error ?? "Unknown error"}
            onRetry={() => this.setState({ error: null })}
          />
        </div>
      );
    }
    return this.props.children;
  }
}

type Route =
  | { kind: "onboarding" }
  | {
      kind: "session";
      sessionId: string;
      domain: Domain;
      openingMessage: string;
      originalQuery: string;
    }
  | { kind: "wrap_up"; sessionId: string };

export default function App() {
  const [route, setRoute] = useState<Route>({ kind: "onboarding" });

  switch (route.kind) {
    case "onboarding":
      return (
        <ErrorBoundary>
          <OnboardingView
            onSessionStart={(sessionId, openingMessage, domain, originalQuery) =>
              setRoute({
                kind: "session",
                sessionId,
                domain,
                openingMessage,
                originalQuery,
              })
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
            originalQuery={route.originalQuery}
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
