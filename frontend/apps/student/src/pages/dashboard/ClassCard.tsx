// frontend/apps/student/src/pages/dashboard/ClassCard.tsx
import { Link } from "react-router-dom";
import { getMasteryStyle } from "@kaihle/types";
import type { ClassSummary } from "../../hooks/useStudentDashboard";

interface ClassCardProps {
  data: ClassSummary;
}

const TREND_CONFIG = {
  up: { symbol: "↑", colorClass: "text-green-600" },
  down: { symbol: "↓", colorClass: "text-red-500" },
  flat: { symbol: "→", colorClass: "text-brand-muted" },
  none: { symbol: "", colorClass: "" },
} as const;

export function ClassCard({ data }: ClassCardProps) {
  const { dotClass, textClass, label } = getMasteryStyle(data.mastery_score);
  const trend = TREND_CONFIG[data.trend];
  const assessedPct =
    data.topics_total > 0
      ? Math.round((data.topics_assessed / data.topics_total) * 100)
      : 0;
  const masteryPct =
    data.mastery_score !== null ? Math.round(data.mastery_score * 100) : null;

  return (
    <div className="bg-white border border-brand-border rounded-card hover:border-brand-primary transition-colors flex flex-col">
      <Link
        to={`/student/classes/${data.class_id}`}
        className="block p-4 flex-1"
        aria-label={data.class_name}
      >
        <div className="flex items-start gap-3">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold font-display text-sm flex-shrink-0 ${data.subject_color}`}
            aria-hidden="true"
          >
            {data.subject_name[0]}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-bold text-brand-ink leading-tight">
              {data.class_name}
            </div>
            <div className="text-xs text-brand-muted mt-0.5">
              {data.teacher_name}
            </div>
          </div>
          {masteryPct !== null && (
            <div
              className={`font-display font-bold text-2xl leading-none flex-shrink-0 ${textClass}`}
            >
              {masteryPct}%
            </div>
          )}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
            aria-label={label}
            role="img"
          />
          <span className={`text-xs font-semibold ${textClass}`}>{label}</span>
          {trend.symbol && (
            <span
              className={`text-xs font-bold ml-auto ${trend.colorClass}`}
              aria-hidden="true"
            >
              {trend.symbol}
            </span>
          )}
        </div>

        <div className="mt-2">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-brand-muted font-medium">
              {data.topics_assessed}/{data.topics_total} topics assessed
            </span>
            <span className="text-xs font-bold text-brand-body">
              {assessedPct}%
            </span>
          </div>
          <div
            className="w-full bg-brand-border rounded-full h-1.5"
            role="progressbar"
            aria-valuenow={assessedPct}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="bg-brand-primary h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${assessedPct}%` }}
            />
          </div>
        </div>

        {data.diagnostic_status === "PENDING" && (
          <div className="mt-3 text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-1.5">
            Take your diagnostic to unlock your study plan →
          </div>
        )}
      </Link>

      <div className="border-t border-brand-border-soft px-4 py-2.5">
        <Link
          to={`/student/classes/${data.class_id}`}
          className="flex items-center justify-center gap-1.5 text-xs font-semibold text-brand-primary hover:text-brand-primary/80 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
          onClick={(e) => e.stopPropagation()}
        >
          View class
          <svg
            className="w-3.5 h-3.5"
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M3 8h10M9 4l4 4-4 4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </Link>
      </div>
    </div>
  );
}
