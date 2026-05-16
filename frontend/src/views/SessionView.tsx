import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileText } from "lucide-react";
import type { Phase, Subproblem, UIDirective, ToolCall, Domain } from "../api/types";
import { api } from "../api/client";
import ChatPane, { type ChatMessage } from "../components/ChatPane";
import SubproblemPanel from "../components/SubproblemPanel";
import ToolPane from "../components/ToolPane";
import PhaseStepper from "../components/PhaseStepper";
import MathText from "../components/MathText";
import { Brandmark } from "../components/brand/Brandmark";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { lookup } from "../specializations/registry";

// Directives that require a single-click answer and should block chat input
// until the student responds. Display-only / type-into-chat directives
// (ReflectionPrompt, PseudocodePad, OutlineTree) are intentionally excluded.
export const INTERACTIVE_DIRECTIVES = new Set([
  "CalibrationCheck",
  "ConfidenceWidget",
  "RuleRecallPrompt",
]);

const VALID_LIFETIMES = new Set<UIDirective["lifetime"]>([
  "until_dismissed",
  "until_next_turn",
  "persistent_in_subproblem",
]);

// Normalize unknown / missing lifetime values to until_next_turn so the
// directive is guaranteed to be cleared on the next student turn rather than
// sticking around forever.
export function normalizeDirective(d: UIDirective): UIDirective {
  if (VALID_LIFETIMES.has(d.lifetime)) return d;
  return { ...d, lifetime: "until_next_turn" };
}

// Stable string key for a directive — used to identify dismissed instances
// (UIDirective has no server-assigned id field).
export function directiveKey(d: UIDirective): string {
  return `${d.placement}::${d.component}::${JSON.stringify(d.props)}`;
}

// Active subproblem id, or null. Used to detect transitions so we can clear
// persistent_in_subproblem directives when the focus changes.
export function getActiveSubproblemId(subproblems: Subproblem[]): string | null {
  return subproblems.find((s) => s.status === "active")?.id ?? null;
}

// Pure helper: merge new side-panel directives into an existing list,
// dropping duplicates of (component, props). Prevents the panel from growing
// unbounded when the agent re-emits the same directive every turn.
export function mergeSidePanelDirectives(
  prev: UIDirective[],
  incoming: UIDirective[],
): UIDirective[] {
  if (incoming.length === 0) return prev;
  const key = (d: UIDirective) => `${d.component}::${JSON.stringify(d.props)}`;
  const seen = new Set(prev.map(key));
  const fresh = incoming.filter((d) => !seen.has(key(d)));
  return fresh.length === 0 ? prev : [...prev, ...fresh];
}

// Pure helper: returns true if the last assistant message has an interactive
// inline directive whose component is actually registered. Unknown components
// and display-only directives must not lock the input.
export function isAwaitingDirective(
  messages: ChatMessage[],
  componentExists: (key: string) => boolean,
): boolean {
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  return Boolean(
    lastAssistant?.directives?.some(
      (d) =>
        d.placement === "inline" &&
        INTERACTIVE_DIRECTIVES.has(d.component) &&
        componentExists(`${d.domain}.${d.component}`),
    ),
  );
}

export default function SessionView({
  sessionId,
  domain,
  openingMessage,
  originalQuery,
  onWrapUp,
  onOnboardingComplete,
}: {
  sessionId: string;
  domain: Domain;
  openingMessage: string;
  originalQuery: string;
  onWrapUp: () => void;
  onOnboardingComplete?: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: openingMessage },
  ]);
  const [subproblems, setSubproblems] = useState<Subproblem[]>([]);
  const [phase, setPhase] = useState<Phase>("clarification");
  const [sidePanelDirectives, setSidePanelDirectives] = useState<UIDirective[]>([]);
  const [toolResults, setToolResults] = useState<ToolCall[]>([]);
  const [modalDirective, setModalDirective] = useState<UIDirective | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [problemOpen, setProblemOpen] = useState(false);
  const problemBtnRef = useRef<HTMLButtonElement | null>(null);
  // Synchronous lock — isLoading state updates asynchronously, so rapid Enter
  // presses or directive clicks could otherwise double-fire before the disabled
  // state takes effect. A ref flips immediately and is checked at entry.
  const inFlightRef = useRef(false);

  async function send(message?: string, directiveResponse?: { component: string; value: unknown }) {
    setIsLoading(true);

    // Clear until_next_turn directives from previous turn
    setMessages((prev) =>
      prev.map((m) =>
        m.role === "assistant"
          ? { ...m, directives: m.directives?.filter((d) => d.lifetime !== "until_next_turn") }
          : m
      )
    );
    setSidePanelDirectives((prev) =>
      prev.filter((d) => d.lifetime !== "until_next_turn")
    );

    try {
      const req = { session_id: sessionId } as Parameters<typeof api.chat>[0];
      if (message) req.message = message;
      if (directiveResponse) req.directive_response = directiveResponse;
      const res = await api.chat(req);

      const allDirectives = (res.ui_directives ?? []).map(normalizeDirective);
      const inlineDirectives = allDirectives.filter((d) => d.placement === "inline");
      const sidePanelNew = allDirectives.filter((d) => d.placement === "side_panel");
      const modalNew = allDirectives.filter((d) => d.placement === "modal");

      // Skip empty assistant messages (backend sends reply: null on tool-only turns).
      // Still push if there are inline directives to render.
      if (res.reply || inlineDirectives.length > 0) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: res.reply ?? "", directives: inlineDirectives },
        ]);
      }

      if (res.subproblems?.length > 0) setSubproblems(res.subproblems);
      if (res.phase) setPhase(res.phase);
      if (sidePanelNew.length > 0) {
        setSidePanelDirectives((prev) =>
          mergeSidePanelDirectives(prev, sidePanelNew),
        );
      }
      if (res.tool_calls?.length > 0) setToolResults(res.tool_calls);
      if (modalNew.length > 0) setModalDirective(modalNew[0]);

      if (res.onboarding_complete) {
        // Persona intake finished — go back to onboarding so user can enter problem
        setTimeout(() => onOnboardingComplete?.(), 1200);
      } else if (res.phase === "wrap_up") {
        // Small delay so the wrap-up message is visible before transitioning
        setTimeout(onWrapUp, 1800);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setIsLoading(false);
      inFlightRef.current = false;
    }
  }

  function handleSend(text: string) {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    send(text);
  }

  function handleDismissDirective(key: string) {
    setMessages((prev) =>
      prev.map((m) =>
        m.role === "assistant" && m.directives
          ? {
              ...m,
              directives: m.directives.filter((d) => directiveKey(d) !== key),
            }
          : m,
      ),
    );
    setSidePanelDirectives((prev) =>
      prev.filter((d) => directiveKey(d) !== key),
    );
  }

  // Clear persistent_in_subproblem directives when the active subproblem
  // changes. Tracked by ref so we don't fire on the initial render.
  const lastActiveSpRef = useRef<string | null>(null);
  useEffect(() => {
    const active = getActiveSubproblemId(subproblems);
    if (active !== lastActiveSpRef.current) {
      const prevActive = lastActiveSpRef.current;
      lastActiveSpRef.current = active;
      if (prevActive !== null) {
        setMessages((prev) =>
          prev.map((m) =>
            m.role === "assistant" && m.directives
              ? {
                  ...m,
                  directives: m.directives.filter(
                    (d) => d.lifetime !== "persistent_in_subproblem",
                  ),
                }
              : m,
          ),
        );
        setSidePanelDirectives((prev) =>
          prev.filter((d) => d.lifetime !== "persistent_in_subproblem"),
        );
      }
    }
  }, [subproblems]);

  function formatDirectiveValue(component: string, value: unknown): string {
    if (component === "CalibrationCheck" && typeof value === "number") {
      return `My confidence: ${value}/5`;
    }
    if (component === "ConfidenceWidget" && typeof value === "number") {
      return `Confidence in solution: ${value}/5`;
    }
    if (component === "RuleRecallPrompt" && typeof value === "string") {
      return value;
    }
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
    return JSON.stringify(value);
  }

  function handleDirectiveResponse(component: string, value: unknown) {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    // Only close the modal if the response IS for the modal directive.
    // Answering an unrelated inline widget should not dismiss an open modal.
    if (modalDirective && modalDirective.component === component) {
      setModalDirective(null);
    }
    const text = formatDirectiveValue(component, value);
    setMessages((prev) => {
      const cleared = prev.map((m, i) =>
        m.role === "assistant" && i === prev.length - 1
          ? { ...m, directives: m.directives?.filter((d) => d.component !== component) }
          : m,
      );
      return [...cleared, { role: "user", content: text }];
    });
    send(undefined, { component, value });
  }

  const awaitingDirective = isAwaitingDirective(
    messages,
    (key) => lookup(key) !== undefined,
  );

  useEffect(() => {
    if (!modalDirective) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalDirective(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalDirective]);

  useEffect(() => {
    if (!problemOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setProblemOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      const popover = document.getElementById("original-problem-popover");
      const btn = problemBtnRef.current;
      const target = e.target as Node;
      if (popover?.contains(target) || btn?.contains(target)) return;
      setProblemOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [problemOpen]);

  return (
    <div className="flex h-screen bg-paper overflow-hidden">
      <a
        href="#chat-pane"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-accent focus:text-white focus:px-3 focus:py-1.5 focus:rounded-md focus:text-body-emphasis"
      >
        Skip to chat
      </a>
      {/* Main column */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Header */}
        <header className="flex items-center justify-between gap-4 px-5 py-3 border-b border-rule bg-paper shrink-0">
          <div className="flex items-center gap-3 shrink-0">
            <Brandmark size={24} />
            <span className="font-mono text-mono text-ink-soft capitalize">
              {domain}
            </span>
          </div>
          <div className="flex-1 flex justify-center min-w-0">
            {domain !== "persona" && <PhaseStepper phase={phase} />}
          </div>
          <div className="flex items-center gap-2 shrink-0 relative">
            {originalQuery && (
              <button
                ref={problemBtnRef}
                onClick={() => setProblemOpen((o) => !o)}
                aria-expanded={problemOpen}
                aria-controls="original-problem-popover"
                className="inline-flex items-center gap-1.5 text-caption text-ink-soft hover:text-ink border border-rule rounded-md px-2 py-1 transition-colors"
              >
                <FileText size={12} strokeWidth={1.8} />
                Problem
              </button>
            )}
            <ThemeToggle />
            <button
              onClick={onWrapUp}
              className="text-caption text-ink-faint hover:text-ink-soft transition-colors px-2 py-1"
            >
              End session →
            </button>

            <AnimatePresence>
              {problemOpen && (
                <motion.div
                  id="original-problem-popover"
                  role="dialog"
                  aria-label="Original problem"
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
                  className="absolute right-0 top-full mt-2 w-[min(420px,90vw)] z-40 bg-surface border border-rule rounded-md shadow-lg p-4 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-label text-ink-faint">Original problem</p>
                    <button
                      onClick={() => setProblemOpen(false)}
                      aria-label="Close"
                      className="text-caption text-ink-faint hover:text-ink-soft"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="text-body text-ink leading-relaxed max-h-64 overflow-y-auto">
                    <MathText>{originalQuery}</MathText>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </header>

        <div id="chat-pane" className="flex flex-col flex-1 min-h-0">
          <ChatPane
            messages={messages}
            isLoading={isLoading}
            inputDisabled={awaitingDirective}
            onSend={handleSend}
            onDirectiveResponse={handleDirectiveResponse}
            onDismissDirective={handleDismissDirective}
            domain={domain}
          />
        </div>
      </div>

      {/* Subproblem sidebar — always rendered; shows empty state pre-decomposition */}
      <SubproblemPanel subproblems={subproblems} />

      {/* Tool pane */}
      <ToolPane
        directives={sidePanelDirectives}
        toolResults={toolResults}
        domain={domain}
        onDirectiveResponse={handleDirectiveResponse}
        onDismissDirective={handleDismissDirective}
      />

      {/* Modal overlay — only mount if the component is registered */}
      <AnimatePresence>
        {modalDirective && (() => {
          const Component = lookup(`${modalDirective.domain}.${modalDirective.component}`);
          if (!Component) return null;
          return (
            <motion.div
              key="modal"
              role="dialog"
              aria-modal="true"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-ink/40 backdrop-blur-sm flex items-center justify-center z-50 p-4"
              onClick={() => setModalDirective(null)}
            >
              <motion.div
                initial={{ opacity: 0, y: 12, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 12, scale: 0.97 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                onClick={(e) => e.stopPropagation()}
                className="bg-surface border border-rule rounded-lg shadow-xl p-6 max-w-sm w-full space-y-4"
              >
                <Component
                  {...modalDirective.props}
                  onSelect={(value: unknown) =>
                    handleDirectiveResponse(modalDirective.component, value)
                  }
                />
                <button
                  onClick={() => setModalDirective(null)}
                  aria-label="Dismiss dialog"
                  className="w-full text-caption text-ink-faint hover:text-ink-soft transition-colors"
                >
                  Dismiss (Esc)
                </button>
              </motion.div>
            </motion.div>
          );
        })()}
      </AnimatePresence>
    </div>
  );
}
