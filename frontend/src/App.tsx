import { useState } from "react";
import OnboardingView from "./views/OnboardingView";
import SessionView from "./views/SessionView";
import WrapUpView from "./views/WrapUpView";

type Route =
  | { kind: "onboarding" }
  | { kind: "session"; sessionId: string }
  | { kind: "wrap_up"; sessionId: string };

export default function App() {
  const [route, setRoute] = useState<Route>({ kind: "onboarding" });

  switch (route.kind) {
    case "onboarding":
      return (
        <OnboardingView
          onSessionStart={(sessionId) => setRoute({ kind: "session", sessionId })}
        />
      );
    case "session":
      return (
        <SessionView
          sessionId={route.sessionId}
          onWrapUp={() => setRoute({ kind: "wrap_up", sessionId: route.sessionId })}
        />
      );
    case "wrap_up":
      return (
        <WrapUpView
          sessionId={route.sessionId}
          onRestart={() => setRoute({ kind: "onboarding" })}
        />
      );
  }
}
