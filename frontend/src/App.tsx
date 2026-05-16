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
  | { kind: "onboarding"; initialStep?: "username" | "query"; initialUsername?: string }
  | { kind: "persona_session"; sessionId: string; openingMessage: string; username: string }
  | { kind: "session"; sessionId: string; domain: Domain; openingMessage: string; originalQuery: string }
  | { kind: "wrap_up"; sessionId: string };

export default function App() {
  const [route, setRoute] = useState<Route>({ kind: "onboarding" });

  switch (route.kind) {
    case "onboarding":
      return (
        <ErrorBoundary>
          <OnboardingView
            initialStep={route.initialStep}
            initialUsername={route.initialUsername}
            onSessionStart={(sessionId, openingMessage, domain, originalQuery) =>
              setRoute({ kind: "session", sessionId, domain, openingMessage, originalQuery })
            }
            onPersonaSession={(sessionId, openingMessage, username) =>
              setRoute({ kind: "persona_session", sessionId, openingMessage, username })
            }
          />
        </ErrorBoundary>
      );
    case "persona_session": {
      const { sessionId, openingMessage, username } = route;
      return (
        <ErrorBoundary>
          <SessionView
            sessionId={sessionId}
            domain="persona"
            openingMessage={openingMessage}
            originalQuery=""
            onWrapUp={() => setRoute({ kind: "onboarding" })}
            onOnboardingComplete={() => {
              // Persona intake done — send user to Step 2 to type their problem
              setRoute({ kind: "onboarding", initialStep: "query", initialUsername: username });
            }}
          />
        </ErrorBoundary>
      );
    }
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
