import { useState } from "react";

export default function PseudocodePad({
  prompt,
  initial_value,
}: {
  prompt: string;
  initial_value?: string;
}) {
  const [value, setValue] = useState(initial_value ?? "");
  return (
    <div data-testid="pseudocode-pad">
      <label>{prompt}</label>
      <textarea value={value} onChange={(e) => setValue(e.target.value)} />
    </div>
  );
}
