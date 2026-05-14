// Renders the thinking trace as a narrative reflection, not a dashboard.
// Centrepiece is the understanding delta (initial → final).

export default function WrapUpView({
  sessionId,
  onRestart,
}: {
  sessionId: string;
  onRestart: () => void;
}) {
  return (
    <main data-testid="wrap-up-view">
      <p>wrap-up for {sessionId}</p>
      <button onClick={onRestart}>New session</button>
    </main>
  );
}
