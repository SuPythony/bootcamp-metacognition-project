/**
 * Renders a string that may contain LaTeX ($...$ or $$...$$) and markdown.
 * Used for assistant chat messages and any component that receives model text.
 */
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface Props {
  children: string;
  className?: string;
  /** If true, strips outer <p> wrapper so it renders inline */
  inline?: boolean;
}

export default function MathText({ children, className, inline }: Props) {
  return (
    <span className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={
          inline
            ? {
                // Suppress the wrapping <p> for single-line inline use
                p: ({ children: c }) => <span>{c}</span>,
              }
            : {
                p: ({ children: c }) => (
                  <p className="mb-1 last:mb-0">{c}</p>
                ),
                code: ({ children: c }) => (
                  <code className="bg-gray-200 text-gray-800 rounded px-1 py-0.5 text-xs font-mono">
                    {c}
                  </code>
                ),
                pre: ({ children: c }) => (
                  <pre className="bg-gray-200 text-gray-800 rounded p-2 text-xs font-mono overflow-x-auto my-1">
                    {c}
                  </pre>
                ),
              }
        }
      >
        {children}
      </ReactMarkdown>
    </span>
  );
}
