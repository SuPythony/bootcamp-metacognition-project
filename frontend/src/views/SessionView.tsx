// Main tutoring surface. Composes ChatPane + SubproblemPanel + ToolPane and
// dispatches ui_directives from /chat through the specializations registry.

export default function SessionView({
  sessionId,
  onWrapUp,
}: {
  sessionId: string;
  onWrapUp: () => void;
}) {
  return (
    <main data-testid="session-view">
      <p>session {sessionId}</p>
      <button onClick={onWrapUp}>Wrap up</button>
    </main>
  );
}
