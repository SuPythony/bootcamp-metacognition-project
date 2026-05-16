import { useState } from "react";
import { Check, Copy } from "lucide-react";

export default function CodeOutput({
  stdout,
  stderr,
  exit_code,
}: {
  stdout: string;
  stderr: string;
  exit_code: number;
}) {
  const [copied, setCopied] = useState(false);
  const ok = exit_code === 0;
  const combined = [stdout, stderr].filter(Boolean).join("\n");

  function handleCopy() {
    void navigator.clipboard.writeText(combined).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    });
  }

  return (
    <div className="rounded-md border border-rule overflow-hidden bg-[#14130F]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#1C1B17] border-b border-[#2F2C25]">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#3F3B33]" aria-hidden />
          <span className="h-2 w-2 rounded-full bg-[#3F3B33]" aria-hidden />
          <span className="h-2 w-2 rounded-full bg-[#3F3B33]" aria-hidden />
          <span className="ml-2 text-label text-[#B8B3A6]">Output</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-label px-1.5 py-0.5 rounded ${
              ok
                ? "text-[#A6C39A] bg-[#A6C39A]/10"
                : "text-[#E08471] bg-[#E08471]/10"
            }`}
          >
            exit {exit_code}
          </span>
          <button
            onClick={handleCopy}
            aria-label="Copy output"
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-caption text-[#B8B3A6] hover:text-[#EDEAE0] hover:bg-[#2F2C25] transition-colors"
          >
            {copied ? (
              <>
                <Check size={11} strokeWidth={2} />
                copied
              </>
            ) : (
              <>
                <Copy size={11} strokeWidth={1.8} />
                copy
              </>
            )}
          </button>
        </div>
      </div>
      <pre
        data-testid="code-output"
        className="px-3 py-2.5 font-mono text-mono leading-relaxed text-[#EDEAE0] whitespace-pre-wrap"
      >
        {stdout && (
          <span>
            <span className="text-[#6E6A60] select-none">$ </span>
            {stdout}
          </span>
        )}
        {stderr && (
          <span className="block text-[#E08471] mt-1">
            <span className="select-none">! </span>
            {stderr}
          </span>
        )}
        {!stdout && !stderr && (
          <span className="text-[#6E6A60] italic">(no output)</span>
        )}
      </pre>
    </div>
  );
}
