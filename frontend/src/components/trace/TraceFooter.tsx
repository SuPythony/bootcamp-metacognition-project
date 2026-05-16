import type { ThinkingTrace } from "../../api/types";
import { HandDrawnRule } from "./HandDrawnRule";

function buildClosingLine(trace: ThinkingTrace, dateISO: string): string {
  const parts = trace.subproblems?.length ?? 0;
  const corrections =
    typeof trace.self_corrections === "number" ? trace.self_corrections : 0;
  const turns =
    typeof trace.total_turns === "number" ? trace.total_turns : 0;
  const date = new Date(dateISO).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  if (parts === 0 && corrections === 0) {
    return `On ${date}, you worked through one problem in ${turns} turns.`;
  }

  const partsClause =
    parts > 0
      ? `decomposed ${parts} part${parts !== 1 ? "s" : ""}`
      : "worked end-to-end";
  const correctionsClause =
    corrections > 0
      ? ` and changed your mind ${corrections === 1 ? "once" : `${corrections} times`}`
      : "";

  return `On ${date}, you ${partsClause}${correctionsClause}.`;
}

export function TraceFooter({
  trace,
  dateISO,
}: {
  trace: ThinkingTrace;
  dateISO?: string;
}) {
  const date = dateISO ?? new Date().toISOString();
  return (
    <section className="space-y-3">
      <HandDrawnRule />
      <p className="font-display text-serif-lede text-ink leading-snug">
        {buildClosingLine(trace, date)}
      </p>
    </section>
  );
}
