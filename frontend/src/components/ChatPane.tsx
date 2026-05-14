import { useState, useRef, useEffect } from "react";
import type { UIDirective, Domain } from "../api/types";
import { lookup } from "../specializations/registry";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  directives?: UIDirective[];
}

export default function ChatPane({
  messages,
  isLoading,
  onSend,
  onDirectiveResponse,
  domain,
}: {
  messages: ChatMessage[];
  isLoading: boolean;
  onSend: (text: string) => void;
  onDirectiveResponse?: (component: string, value: unknown) => void;
  domain?: Domain;
}) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  function handleSend() {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    onSend(text);
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i}>
            <div
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-900 rounded-bl-sm"
                }`}
              >
                {msg.content}
              </div>
            </div>

            {/* Inline directives below the last assistant message */}
            {msg.role === "assistant" &&
              msg.directives
                ?.filter((d) => d.placement === "inline")
                .map((d, j) => {
                  const key = `${d.domain}.${d.component}`;
                  const Component = lookup(key);
                  if (!Component) return null;
                  return (
                    <div key={j} className="mt-2 ml-2">
                      <Component
                        {...d.props}
                        onSelect={(value: unknown) =>
                          onDirectiveResponse?.(d.component, value)
                        }
                        domain={domain}
                      />
                    </div>
                  );
                })}
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-400 italic">
              Thinking…
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t bg-white px-4 py-3 flex gap-2 items-end">
        <textarea
          className="flex-1 resize-none border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 leading-relaxed"
          rows={2}
          placeholder="Type your answer… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium disabled:opacity-40 hover:bg-indigo-700 transition-colors shrink-0"
        >
          Send
        </button>
      </div>
    </div>
  );
}
