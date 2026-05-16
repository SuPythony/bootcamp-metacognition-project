import { useState } from "react";
import { ChevronRight } from "lucide-react";

interface OutlineNode {
  id: string;
  parent_id: string | null;
  label: string;
  claim?: string;
}

interface TreeNode extends OutlineNode {
  children: TreeNode[];
}

function buildTree(nodes: OutlineNode[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  nodes.forEach((n) => byId.set(n.id, { ...n, children: [] }));
  const roots: TreeNode[] = [];
  byId.forEach((n) => {
    if (n.parent_id && byId.has(n.parent_id)) {
      byId.get(n.parent_id)!.children.push(n);
    } else {
      roots.push(n);
    }
  });
  return roots;
}

function NodeRow({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;

  return (
    <li className="relative">
      {depth > 0 && (
        <span
          className="absolute -left-3 top-3 w-3 h-px bg-rule"
          aria-hidden
        />
      )}
      <div className="flex items-start gap-1.5 py-1">
        {hasChildren ? (
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? "Collapse" : "Expand"}
            aria-expanded={open}
            className="mt-0.5 text-ink-faint hover:text-ink transition-colors"
          >
            <ChevronRight
              size={12}
              strokeWidth={1.8}
              className={`transition-transform ${open ? "rotate-90" : ""}`}
            />
          </button>
        ) : (
          <span
            className="mt-1.5 inline-block w-1 h-1 rounded-full bg-ink-faint shrink-0"
            aria-hidden
          />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-body-emphasis text-ink leading-snug">{node.label}</p>
          {node.claim && (
            <p className="font-display italic text-caption text-ink-soft mt-0.5">
              {node.claim}
            </p>
          )}
        </div>
      </div>
      {hasChildren && open && (
        <ul className="ml-3 pl-3 border-l border-rule space-y-0.5">
          {node.children.map((c) => (
            <NodeRow key={c.id} node={c} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function OutlineTree({ nodes }: { nodes: OutlineNode[] }) {
  const roots = buildTree(nodes);
  return (
    <ul data-testid="outline-tree" className="space-y-0.5">
      {roots.map((n) => (
        <NodeRow key={n.id} node={n} depth={0} />
      ))}
    </ul>
  );
}
