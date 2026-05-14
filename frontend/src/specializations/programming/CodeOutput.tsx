export default function CodeOutput({
  stdout,
  stderr,
  exit_code,
}: {
  stdout: string;
  stderr: string;
  exit_code: number;
}) {
  return (
    <pre data-testid="code-output">
      {stdout}
      {stderr && <span style={{ color: "red" }}>{stderr}</span>}
      <div>exit {exit_code}</div>
    </pre>
  );
}
