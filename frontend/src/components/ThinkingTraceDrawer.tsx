import type { ThinkingTrace } from "../api/types";
import { TraceHero } from "./trace/TraceHero";
import { TraceTimeline } from "./trace/TraceTimeline";
import { CalibrationPlot } from "./trace/CalibrationPlot";
import { TraceNumbers } from "./trace/TraceNumbers";
import { TraceFooter } from "./trace/TraceFooter";

export default function ThinkingTraceDrawer({
  trace,
  domain,
  dateISO,
}: {
  trace: ThinkingTrace;
  domain?: string;
  dateISO?: string;
}) {
  return (
    <article data-testid="thinking-trace-drawer" className="space-y-10">
      <TraceHero trace={trace} domain={domain} dateISO={dateISO} />
      <TraceTimeline trace={trace} />
      <CalibrationPlot trace={trace} />
      <TraceNumbers trace={trace} />
      <TraceFooter trace={trace} dateISO={dateISO} />
    </article>
  );
}
