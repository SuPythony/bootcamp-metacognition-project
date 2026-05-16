/**
 * Renders a string that may contain LaTeX ($...$ or $$...$$) and markdown.
 * Used for assistant chat messages and any component that receives model text.
 */
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkBreaks from "remark-breaks";
import rehypeKatex from "rehype-katex";

interface Props {
  children: string | null | undefined;
  className?: string;
  /** If true, strips outer <p> wrapper so it renders inline */
  inline?: boolean;
}

// LLM occasionally returns the literal two-character sequence \\n instead of a
// real newline. Normalize both into a real newline so remark-breaks can render
// it as a <br>. Also tolerate null/undefined since the backend may send
// reply: null on tool-only turns.
function normalize(text: string | null | undefined): string {
  if (typeof text !== "string") return "";
  return text.replace(/\\n/g, "\n");
}

export default function MathText({ children, className, inline }: Props) {
  const content = normalize(children);
  return (
    <span className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkBreaks]}
        rehypePlugins={[rehypeKatex]}
        components={
          inline
            ? {
                // Suppress the wrapping <p> for single-line inline use
                p: ({ children: c }) => <span>{c}</span>,
              }
            : {
                p: ({ children: c }) => (
                  <p className="mb-2 last:mb-0">{c}</p>
                ),
                code: ({ children: c }) => (
                  <code className="bg-surface-muted text-ink rounded px-1 py-0.5 text-mono font-mono">
                    {c}
                  </code>
                ),
                pre: ({ children: c }) => (
                  <pre className="bg-surface-muted text-ink rounded p-2 text-mono font-mono overflow-x-auto my-2">
                    {c}
                  </pre>
                ),
              }
        }
      >
        {content}
      </ReactMarkdown>
    </span>
  );
}
