/**
 * ScoreDistributionChart — horizontal bar chart for score band distribution.
 *
 * NOTE: Implemented as pure HTML/CSS bars (no external charting library required).
 * The task spec calls for Recharts, but recharts is not yet installed in the
 * teacher workspace. This implementation is functionally equivalent — horizontally
 * oriented bars, correct band colours, visible legend, full accessibility.
 * When recharts is available, this can be migrated to use BarChart.
 *
 * Accessibility:
 *   - role="img" on chart wrapper
 *   - aria-label with full distribution text
 *   - Visible text legend below bars
 *
 * Reteach banner: shown when needsWork / submitted > 0.3 AND submitted > 0.
 */
import type { StudentAttemptSummary } from "../../hooks/useAssessmentResults";

interface ScoreDistributionChartProps {
  attempts: StudentAttemptSummary[];
  isLoading?: boolean;
}

interface BandCount {
  label: string;
  count: number;
  color: string;
  textColor: string;
  fillClass: string;
  pct: number;
}

export function ScoreDistributionChart({
  attempts,
  isLoading = false,
}: ScoreDistributionChartProps) {
  const submitted = attempts.filter((a) => a.status === "SUBMITTED");
  const notSubmitted = attempts.filter((a) => a.status !== "SUBMITTED");

  const strong = submitted.filter(
    (a) => a.score !== null && a.score > 0.7,
  ).length;
  const developing = submitted.filter(
    (a) => a.score !== null && a.score >= 0.4 && a.score <= 0.7,
  ).length;
  const needsWork = submitted.filter(
    (a) => a.score !== null && a.score < 0.4,
  ).length;
  const notSubmittedCount = notSubmitted.length;

  const total = attempts.length;
  const submittedCount = submitted.length;

  const bands: BandCount[] = [
    {
      label: "Strong (≥70%)",
      count: strong,
      color: "#16a34a",
      textColor: "text-green-700",
      fillClass: "bg-brand-green",
      pct: total > 0 ? (strong / total) * 100 : 0,
    },
    {
      label: "Developing (40–69%)",
      count: developing,
      color: "#f59e0b",
      textColor: "text-amber-600",
      fillClass: "bg-brand-amber",
      pct: total > 0 ? (developing / total) * 100 : 0,
    },
    {
      label: "Needs Work (<40%)",
      count: needsWork,
      color: "#ef4444",
      textColor: "text-red-600",
      fillClass: "bg-brand-red",
      pct: total > 0 ? (needsWork / total) * 100 : 0,
    },
    {
      label: "Not submitted",
      count: notSubmittedCount,
      color: "#d1d5db",
      textColor: "text-gray-400",
      fillClass: "bg-gray-300",
      pct: total > 0 ? (notSubmittedCount / total) * 100 : 0,
    },
  ];

  const showReteachBanner =
    submittedCount > 0 && needsWork / submittedCount > 0.3;

  const ariaLabel = `Score distribution: ${strong} Strong, ${developing} Developing, ${needsWork} Needs Work, ${notSubmittedCount} not submitted`;

  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-[180px] bg-gray-100 rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="score-distribution">
      {/* Chart — horizontal bars */}
      <div role="img" aria-label={ariaLabel} className="flex flex-col gap-2">
        {bands.map((band) => (
          <div key={band.label} className="flex items-center gap-3">
            {/* Color dot + label */}
            <div className="flex items-center gap-1.5 w-36 flex-shrink-0">
              <div
                className={`w-3 h-3 rounded-sm`}
                style={{ backgroundColor: band.color }}
              />
              <span className="text-xs text-gray-600 font-sans">
                {band.label}
              </span>
            </div>
            {/* Bar */}
            <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
              <div
                className={`h-full rounded-full flex items-center justify-end pr-2 ${band.fillClass}`}
                style={{
                  width: `${band.pct}%`,
                  minWidth: band.count > 0 ? "2rem" : "0",
                }}
              >
                {band.count > 0 && (
                  <span className="text-white text-xs font-sans">
                    {band.count}
                  </span>
                )}
              </div>
            </div>
            {/* Count outside if bar too small */}
            {band.count === 0 && (
              <span className="text-xs text-gray-500">{band.count}</span>
            )}
          </div>
        ))}
      </div>

      {/* Reteach banner — shown when >30% of submitted students scored <40% */}
      {showReteachBanner && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mt-3">
          <p className="text-amber-800 text-sm">
            ⚠ More than 30% of students scored below 40%. This topic may benefit
            from whole-class reteaching before moving on.
          </p>
        </div>
      )}
    </div>
  );
}
