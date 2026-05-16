import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { CornerDownLeft, Send, X } from "lucide-react";
import MathText from "./MathText";
import type { UIDirective, Domain } from "../api/types";
import { lookup } from "../specializations/registry";

function directiveKey(d: UIDirective): string {
  return `${d.placement}::${d.component}::${JSON.stringify(d.props)}`;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  directives?: UIDirective[];
}

function BreathingDots() {
  return (
    <span
      role="status"
      aria-label="Tutor is thinking"
      className="inline-flex items-end gap-1 h-4"
    >
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="block w-1.5 h-1.5 rounded-full bg-ink-faint"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * 0.15,
          }}
        />
      ))}
    </span>
  );
}

function AssistantMessage({ children }: { children: string }) {
  return (
    <div className="pl-4 border-l-2 border-rule space-y-1.5">
      <p className="text-label text-ink-faint">Tutor</p>
      <div className="text-body text-ink leading-relaxed">
        <MathText>{children}</MathText>
      </div>
    </div>
  );
}

function UserMessage({ children }: { children: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] bg-accent-soft text-ink rounded-md px-4 py-2.5 text-body leading-relaxed">
        <span className="whitespace-pre-wrap">{children}</span>
      </div>
    </div>
  );
}

export default function ChatPane({
  messages,
  isLoading,
  inputDisabled,
  onSend,
  onDirectiveResponse,
  onDismissDirective,
  domain,
}: {
  messages: ChatMessage[];
  isLoading: boolean;
  inputDisabled?: boolean;
  onSend: (text: string) => void;
  onDirectiveResponse?: (component: string, value: unknown) => void;
  onDismissDirective?: (key: string) => void;
  domain?: Domain;
}) {
  const disabled = isLoading || inputDisabled === true;
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll only if user is already near the bottom. Otherwise they're
  // scrolled up reading an earlier turn — yanking them back is disorienting.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom < 120) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  function handleSend() {
    const text = input.trim();
    if (!text || disabled) return;
    setInput("");
    onSend(text);
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.map((msg, i) => (
          <div key={i} className="space-y-3">
            {msg.role === "user" ? (
              <UserMessage>{msg.content}</UserMessage>
            ) : (
              <AssistantMessage>{msg.content}</AssistantMessage>
            )}

            {msg.role === "assistant" &&
              msg.directives
                ?.filter((d) => d.placement === "inline")
                .map((d, j) => {
                  const key = `${d.domain}.${d.component}`;
                  const Component = lookup(key);
                  if (!Component) return null;
                  const dKey = directiveKey(d);
                  return (
                    <div key={`${j}-${dKey}`} className="pl-4 mt-1 relative group">
                      {onDismissDirective && (
                        <button
                          type="button"
                          onClick={() => onDismissDirective(dKey)}
                          aria-label="Dismiss prompt"
                          className="absolute top-1 right-1 z-10 inline-flex h-5 w-5 items-center justify-center rounded-md text-ink-faint hover:text-ink hover:bg-surface-muted opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                        >
                          <X size={12} strokeWidth={1.8} />
                        </button>
                      )}
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
          <div className="pl-4 border-l-2 border-rule space-y-1.5">
            <p className="text-label text-ink-faint">Tutor</p>
            <BreathingDots />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-rule bg-paper px-6 py-3">
        {inputDisabled && !isLoading && (
          <p className="text-caption text-ink-faint italic mb-2">
            Answer the question above to continue.
          </p>
        )}
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              className="w-full resize-none bg-transparent border-0 border-b border-rule px-0 py-2 pr-12 text-body text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none leading-relaxed transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              rows={2}
              placeholder={
                inputDisabled
                  ? "Pick an option above…"
                  : "Type your answer…"
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={disabled}
            />
            <span
              className="absolute right-1 bottom-3 inline-flex items-center gap-1 text-caption text-ink-faint pointer-events-none"
              aria-hidden
            >
              <CornerDownLeft size={11} strokeWidth={1.8} />
              to send
            </span>
          </div>
          <motion.button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            whileTap={{ scale: 0.94 }}
            transition={{ duration: 0.12 }}
            aria-label="Send message"
            className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-accent text-white disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
          >
            <Send size={16} strokeWidth={1.8} />
          </motion.button>
        </div>
      </div>
    </div>
  );
}
