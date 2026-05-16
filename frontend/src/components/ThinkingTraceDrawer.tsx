import type { ThinkingTrace } from "../api/types";
import MathText from "./MathText";

const DELTA_STYLES: Record<ThinkingTrace["understanding_delta_label"], string> = {
  significant: "text-green-700 bg-green-50 border-green-200",
  moderate: "text-amber-700 bg-amber-50 border-amber-200",
  small: "text-gray-600 bg-gray-100 border-gray-200",
};

const DELTA_TEXT: Record<ThinkingTrace["understanding_delta_label"], string> = {
  significant: "significant shift",
  moderate: "moderate shift",
  small: "small shift",
};

export default function ThinkingTraceDrawer({ trace }: { trace: ThinkingTrace }) {
  const solvedOwn = trace.subproblems.filter(
    (sp) => !sp.direct_answer_requested
  ).length;

  return (
    <div data-testid="thinking-trace-drawer" className="space-y-5">
      {/* Understanding delta — centrepiece */}
      <section className="rounded-xl border bg-indigo-50 border-indigo-100 p-4 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-semibold text-indigo-900">Your thinking, tracked</h3>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
              DELTA_STYLES[trace.understanding_delta_label]
            }`}
          >
            {DELTA_TEXT[trace.understanding_delta_label]}
          </span>
        </div>

        {trace.initial_understanding && (
          <div className="space-y-0.5">
            <p className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wide">
              You started with
            </p>
            <p className="text-sm text-indigo-800 italic">
              "<MathText inline>{trace.initial_understanding}</MathText>"
            </p>
          </div>
        )}

        {trace.final_understanding && (
          <div className="space-y-0.5">
            <p className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wide">
              By the end
            </p>
            <p className="text-sm text-indigo-800 italic">
              "<MathText inline>{trace.final_understanding}</MathText>"
            </p>
          </div>
        )}

        {trace.understanding_delta_evidence && (
          <p className="text-xs text-indigo-600">
            <MathText inline>{trace.understanding_delta_evidence}</MathText>
          </p>
        )}
      </section>

      {/* Stats row */}
      <section className="grid grid-cols-3 gap-3">
        {[
          { value: trace.total_turns, label: "turns" },
          { value: trace.self_corrections, label: "self-corrections", color: "text-green-600" },
          {
            value: trace.direct_answers_requested,
            label: "answers asked for",
            color: "text-amber-600",
          },
        ].map(({ value, label, color }) => (
          <div key={label} className="bg-gray-50 rounded-xl p-3 text-center">
            <p className={`text-2xl font-bold ${color ?? "text-gray-800"}`}>{value}</p>
            <p className="text-[11px] text-gray-500 leading-tight mt-0.5">{label}</p>
          </div>
        ))}
      </section>

      {/* Problem breakdown */}
      {trace.subproblems.length > 0 && (
        <section className="space-y-2">
          <h3 className="font-semibold text-gray-800 text-sm">How you tackled it</h3>
          <p className="text-sm text-gray-500">
            You broke it into {trace.subproblems.length} part
            {trace.subproblems.length !== 1 ? "s" : ""} and solved {solvedOwn} yourself.
          </p>
          <div className="space-y-2">
            {trace.subproblems.map((sp) => (
              <div
                key={sp.id}
                className="flex items-start justify-between text-sm border rounded-xl p-3"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-mono text-xs font-semibold text-gray-500">
                    {sp.id}
                  </span>
                  <p className="text-gray-700 text-sm mt-0.5 leading-snug">
                    <MathText inline>{sp.description}</MathText>
                  </p>
                  {sp.escape_hatch_reflection && (
                    <p className="text-xs text-amber-600 mt-1 italic">
                      You noted: "{sp.escape_hatch_reflection}"
                    </p>
                  )}
                </div>
                <div className="text-xs text-gray-400 ml-3 shrink-0 text-right space-y-0.5">
                  <p>{sp.hints_used} hint{sp.hints_used !== 1 ? "s" : ""}</p>
                  {sp.direct_answer_requested && (
                    <p className="text-amber-500">asked for answer</p>
                  )}
                  {sp.confidence_score !== null && sp.confidence_score !== undefined && (
                    <p>confidence: {sp.confidence_score}/5</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Calibration summary */}
      {trace.calibration_points && trace.calibration_points.length > 0 && (() => {
        const points = trace.calibration_points!;
        const correct = points.filter((p) => p.outcome === "correct").length;
        return (
          <section className="space-y-2">
            <h3 className="font-semibold text-gray-800 text-sm">Calibration</h3>
            <p className="text-sm text-gray-500">
              You made {points.length} prediction{points.length !== 1 ? "s" : ""} — got {correct} right.
            </p>
            <div className="space-y-1">
              {points.map((p, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                  <span className="font-mono text-gray-400">{p.subproblem_id}</span>
                  <span>predicted {p.predicted_confidence}/5</span>
                  {p.outcome && (
                    <span
                      className={
                        p.outcome === "correct"
                          ? "text-green-600"
                          : p.outcome === "partial"
                          ? "text-amber-600"
                          : "text-red-500"
                      }
                    >
                      → {p.outcome}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        );
      })()}

      {/* Reflections */}
      {trace.reflection_prompts && trace.reflection_prompts.filter((r) => r.response).length > 0 && (
        <section className="space-y-2">
          <h3 className="font-semibold text-gray-800 text-sm">Reflections</h3>
          <div className="space-y-3">
            {trace.reflection_prompts
              .filter((r) => r.response)
              .map((r, i) => (
                <div key={i} className="border rounded-xl p-3 space-y-1">
                  <p className="text-xs text-gray-500">{r.question}</p>
                  <p className="text-sm text-gray-800 italic">"{r.response}"</p>
                  {r.quality && (
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                        r.quality === "deep"
                          ? "bg-green-100 text-green-700"
                          : r.quality === "decent"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {r.quality}
                    </span>
                  )}
                </div>
              ))}
          </div>
        </section>
      )}
    </div>
  );
}
