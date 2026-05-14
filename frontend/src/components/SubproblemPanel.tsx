import type { Subproblem } from "../api/types";
import HintBadge from "./HintBadge";
import MathText from "./MathText";

const STATUS_STYLES: Record<Subproblem["status"], string> = {
  pending: "bg-gray-50 border-gray-200 text-gray-500",
  active: "bg-indigo-50 border-indigo-300 text-indigo-800 ring-1 ring-indigo-300",
  solved: "bg-green-50 border-green-200 text-green-800",
};

const STATUS_LABEL: Record<Subproblem["status"], string> = {
  pending: "Pending",
  active: "Working…",
  solved: "Solved ✓",
};

export default function SubproblemPanel({
  subproblems,
}: {
  subproblems: Subproblem[];
}) {
  if (subproblems.length === 0) return null;

  return (
    <aside
      data-testid="subproblem-panel"
      className="w-64 border-l bg-gray-50 flex flex-col"
    >
      <div className="px-4 py-3 border-b">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Problem Breakdown
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {subproblems.map((sp) => (
          <div
            key={sp.id}
            className={`rounded-lg border p-3 text-sm ${STATUS_STYLES[sp.status]}`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-xs font-semibold">{sp.id}</span>
              <div className="flex items-center gap-1.5">
                {sp.hints_given > 0 && <HintBadge count={sp.hints_given} />}
                <span className="text-xs">{STATUS_LABEL[sp.status]}</span>
              </div>
            </div>
            <p className="text-sm leading-snug">
              <MathText inline>{sp.description}</MathText>
            </p>
            {sp.goal && (
              <p className="text-xs mt-1.5 opacity-70 italic">
                → <MathText inline>{sp.goal}</MathText>
              </p>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
