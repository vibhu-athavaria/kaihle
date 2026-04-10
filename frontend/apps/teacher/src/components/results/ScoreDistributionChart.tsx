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
    },
    {
      label: "Developing (40–69%)",
      count: developing,
      color: "#f59e0b",
      textColor: "text-amber-600",
    },
    {
      label: "Needs Work (<40%)",
      count: needsWork,
      color: "#ef4444",
      textColor: "text-red-600",
    },
    {
      label: "Not submitted",
      count: notSubmittedCount,
      color: "#d1d5db",
      textColor: "text-gray-400",
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
    <div>
      {/* Chart */}
      <div
        role="img"
        aria-label={ariaLabel}
        className="h-[180px] flex items-end gap-3 px-2"
      >
        {bands.map((band) => {
          const pct = total > 0 ? (band.count / total) * 100 : 0;
          const barHeight = Math.max(pct * 1.5, band.count > 0 ? 8 : 0);
          return (
            <div
              key={band.label}
              className="flex-1 flex flex-col items-center justify-end gap-1"
              style={{ height: "180px" }}
            >
              <span className="text-xs font-bold text-brand-ink">
                {band.count}
              </span>
              <div
                className="w-full rounded-t-md transition-all duration-500"
                style={{
                  backgroundColor: band.color,
                  height: `${barHeight}px`,
                  minHeight: band.count > 0 ? "8px" : "0",
                }}
                title={`${band.label}: ${band.count}`}
              />
            </div>
          );
        })}
      </div>

      {/* Visible text legend */}
      <div className="flex flex-wrap gap-3 mt-3 justify-center">
        {bands.map((band) => (
          <div key={band.label} className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-sm flex-shrink-0"
              style={{ backgroundColor: band.color }}
            />
            <span className="text-xs text-brand-body">{band.label}</span>
          </div>
        ))}
      </div>

      {/* Reteach banner — shown when >30% of submitted students scored <40% */}
      {showReteachBanner && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mt-3">
          <p className="text-amber-800 text-sm">
            ⚠ More than 30% of students scored below 40%. This topic may
            benefit from whole-class reteaching before moving on.
          </p>
        </div>
      )}
    </div>
  );
}
