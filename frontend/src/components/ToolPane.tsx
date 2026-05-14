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
      className="w-72 border-l bg-white flex flex-col"
    >
      <div className="px-4 py-3 border-b">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Tools
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {toolResults.map((tool, i) => {
          if (!tool.ui_component || !domain) return null;
          const Component = lookup(`${domain}.${tool.ui_component}`);
          if (!Component) {
            return (
              <div key={i} className="text-xs text-gray-400 p-2">
                Unknown component: {tool.ui_component}
              </div>
            );
          }
          return (
            <div key={i} className="rounded-xl border p-3">
              <Component {...(tool.display_data ?? {})} />
            </div>
          );
        })}

        {sidePanelItems.map((d, i) => {
          const Component = lookup(`${d.domain}.${d.component}`);
          if (!Component) {
            return (
              <div key={i} className="text-xs text-gray-400 p-2">
                Unknown: {d.component}
              </div>
            );
          }
          return (
            <div key={i} className="rounded-xl border p-3">
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
