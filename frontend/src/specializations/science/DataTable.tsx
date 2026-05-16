export default function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: Array<Array<string | number>>;
}) {
  return (
    <div className="overflow-auto rounded-md border border-rule bg-paper max-h-80">
      <table
        data-testid="data-table"
        className="w-full border-collapse text-body"
      >
        <thead className="sticky top-0 bg-surface-muted">
          <tr>
            {columns.map((c, i) => (
              <th
                key={`c-${i}`}
                scope="col"
                className="font-display text-body-emphasis text-ink text-left px-3 py-2 border-b border-rule whitespace-nowrap"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-rule last:border-b-0 ${
                i % 2 === 1 ? "bg-surface-muted/40" : ""
              }`}
            >
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={`px-3 py-1.5 ${
                    typeof cell === "number"
                      ? "font-mono text-mono text-ink text-right tabular-nums"
                      : "text-ink"
                  }`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
