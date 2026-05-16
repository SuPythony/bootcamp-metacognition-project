import { useState } from "react";
import type { Phase, Subproblem, UIDirective, ToolCall, Domain } from "../api/types";
import { api } from "../api/client";
import ChatPane, { type ChatMessage } from "../components/ChatPane";
import SubproblemPanel from "../components/SubproblemPanel";
import ToolPane from "../components/ToolPane";
import { lookup } from "../specializations/registry";

const PHASE_LABEL: Record<Phase, string> = {
  clarification: "Clarification",
  decomposition: "Decomposition",
  solving: "Solving",
  wrap_up: "Wrap-up",
};

export default function SessionView({
  sessionId,
  domain,
  openingMessage,
  onWrapUp,
  onOnboardingComplete,
}: {
  sessionId: string;
  domain: Domain;
  openingMessage: string;
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

      const inlineDirectives = res.ui_directives?.filter((d) => d.placement === "inline") ?? [];
      const sidePanelNew = res.ui_directives?.filter((d) => d.placement === "side_panel") ?? [];
      const modalNew = res.ui_directives?.filter((d) => d.placement === "modal") ?? [];

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply, directives: inlineDirectives },
      ]);

      if (res.subproblems?.length > 0) setSubproblems(res.subproblems);
      if (res.phase) setPhase(res.phase);
      if (sidePanelNew.length > 0)
        setSidePanelDirectives((prev) => [...prev, ...sidePanelNew]);
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
    }
  }

  function handleSend(text: string) {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    send(text);
  }

  function handleDirectiveResponse(component: string, value: unknown) {
    setModalDirective(null);
    send(undefined, { component, value });
  }

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      {/* Main column */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b bg-white shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-800 capitalize">
              {domain}
            </span>
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
              {PHASE_LABEL[phase]}
            </span>
          </div>
          <button
            onClick={onWrapUp}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            End session →
          </button>
        </header>

        <ChatPane
          messages={messages}
          isLoading={isLoading}
          onSend={handleSend}
          onDirectiveResponse={handleDirectiveResponse}
          domain={domain}
        />
      </div>

      {/* Subproblem sidebar */}
      {subproblems.length > 0 && (
        <SubproblemPanel subproblems={subproblems} />
      )}

      {/* Tool pane */}
      <ToolPane
        directives={sidePanelDirectives}
        toolResults={toolResults}
        domain={domain}
        onDirectiveResponse={handleDirectiveResponse}
      />

      {/* Modal overlay — only mount if the component is registered */}
      {modalDirective && (() => {
        const Component = lookup(`${modalDirective.domain}.${modalDirective.component}`);
        if (!Component) return null;
        return (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full space-y-4">
              <Component
                {...modalDirective.props}
                onSelect={(value: unknown) =>
                  handleDirectiveResponse(modalDirective.component, value)
                }
              />
              <button
                onClick={() => setModalDirective(null)}
                className="w-full text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
