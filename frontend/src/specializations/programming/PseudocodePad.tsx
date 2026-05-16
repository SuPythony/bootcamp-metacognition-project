import { useState } from "react";

const RULED_BG =
  "repeating-linear-gradient(to bottom, transparent 0, transparent 27px, rgb(var(--color-rule)) 27px, rgb(var(--color-rule)) 28px)";

export default function PseudocodePad({
  prompt,
  initial_value,
}: {
  prompt: string;
  initial_value?: string;
}) {
  const [value, setValue] = useState(initial_value ?? "");
  return (
    <div data-testid="pseudocode-pad" className="space-y-2">
      <p className="font-display text-serif-lede italic text-ink-soft leading-snug">
        {prompt}
      </p>
      <div className="relative rounded-md border border-rule bg-paper overflow-hidden">
        <span
          className="absolute left-0 top-0 bottom-0 w-px bg-alarm/40"
          aria-hidden
        />
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={6}
          spellCheck={false}
          className="relative w-full bg-transparent pl-10 pr-3 py-1 font-mono text-mono text-ink placeholder:text-ink-faint focus:outline-none resize-none"
          style={{
            backgroundImage: RULED_BG,
            backgroundPosition: "0 4px",
            lineHeight: "28px",
          }}
          placeholder="// describe the steps in your own words first…"
        />
      </div>
    </div>
  );
}
