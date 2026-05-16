import type { UIDirective, ToolCall, Domain } from "../api/types";
import { lookup } from "../specializations/registry";

export default function ToolPane({
  directives,
  toolResults,
  domain,
  onDirectiveResponse,
}: {
  directives: UIDirective[];
  toolResults: ToolCall[];
  domain?: Domain;
  onDirectiveResponse?: (component: string, value: unknown) => void;
}) {
  const sidePanelItems = directives.filter((d) => d.placement === "side_panel");
  const hasContent = sidePanelItems.length > 0 || toolResults.length > 0;

  if (!hasContent) return null;

  return (
    <aside
      data-testid="tool-pane"
      className="w-80 border-l border-rule bg-surface flex flex-col shadow-sm"
    >
      <div className="px-4 py-3 border-b border-rule">
        <h2 className="text-label text-ink-faint">Tools</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {toolResults.map((tool, i) => {
          if (!tool.ui_component || !domain) return null;
          const Component = lookup(`${domain}.${tool.ui_component}`);
          if (!Component) {
            return (
              <div key={`t-${i}`} className="text-caption text-ink-faint p-2">
                Unknown component: {tool.ui_component}
              </div>
            );
          }
          return (
            <div key={`t-${i}`} className="rounded-md border border-rule bg-paper p-3">
              <Component {...(tool.display_data ?? {})} />
            </div>
          );
        })}

        {sidePanelItems.map((d, i) => {
          const Component = lookup(`${d.domain}.${d.component}`);
          if (!Component) {
            return (
              <div key={`d-${i}`} className="text-caption text-ink-faint p-2">
                Unknown: {d.component}
              </div>
            );
          }
          return (
            <div key={`d-${i}`} className="rounded-md border border-rule bg-paper p-3">
              <Component
                {...d.props}
                onSelect={(value: unknown) =>
                  onDirectiveResponse?.(d.component, value)
                }
              />
            </div>
          );
        })}
      </div>
    </aside>
  );
}
