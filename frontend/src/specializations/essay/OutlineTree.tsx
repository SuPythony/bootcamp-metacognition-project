interface OutlineNode {
  id: string;
  parent_id: string | null;
  label: string;
  claim?: string;
}

export default function OutlineTree({ nodes }: { nodes: OutlineNode[] }) {
  return (
    <ul data-testid="outline-tree">
      {nodes.map((n) => (
        <li key={n.id}>
          {n.label}
          {n.claim && <em> — {n.claim}</em>}
        </li>
      ))}
    </ul>
  );
}
