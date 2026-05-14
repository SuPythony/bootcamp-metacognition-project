// Username entry + first-query capture. Calls /persona/create; on "pending"
// hands off to a chat loop against the persona session; on "exists" calls
// /session/new and routes to SessionView.

export default function OnboardingView({
  onSessionStart,
}: {
  onSessionStart: (sessionId: string) => void;
}) {
  return (
    <main data-testid="onboarding-view">
      <button onClick={() => onSessionStart("placeholder")}>Start</button>
    </main>
  );
}
