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
  flat: { symbol: "→", colorClass: "text-[#9ca3af]" },
  none: { symbol: "", colorClass: "" },
} as const;

export function ClassCard({ data }: ClassCardProps) {
  const { dotClass, textClass, label } = getMasteryStyle(data.mastery_score);
  const trend = TREND_CONFIG[data.trend];
  const assessedPct =
    data.topics_total > 0
      ? Math.round((data.topics_assessed / data.topics_total) * 100)
      : 0;

  return (
    <Link
      to={`/student/classes/${data.class_id}`}
      className="block bg-white border border-[#e5e7eb] rounded-xl p-4 hover:border-[#1a5c38] transition-colors"
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold font-display text-sm flex-shrink-0 ${data.subject_color}`}
          aria-hidden="true"
        >
          {data.subject_name[0]}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-bold text-[#1a2016] leading-tight">
            {data.class_name}
          </div>
          <div className="text-[11px] text-[#9ca3af] mt-0.5">
            {data.teacher_name}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span
          className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
          aria-label={label}
          role="img"
        />
        <span className={`text-[12px] font-semibold ${textClass}`}>
          {label}
        </span>
        {trend.symbol && (
          <span
            className={`text-[11px] font-bold ml-auto ${trend.colorClass}`}
            aria-hidden="true"
          >
            {trend.symbol}
          </span>
        )}
      </div>

      <div className="mt-2">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[10px] text-[#9ca3af] font-medium">
            {data.topics_assessed}/{data.topics_total} topics assessed
          </span>
          <span className="text-[10px] font-bold text-[#4a5240]">
            {assessedPct}%
          </span>
        </div>
        <div
          className="w-full bg-[#e5e7eb] rounded-full h-1.5"
          role="progressbar"
          aria-valuenow={assessedPct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="bg-[#1a5c38] h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${assessedPct}%` }}
          />
        </div>
      </div>

      {data.diagnostic_status === "PENDING" && (
        <div className="mt-3 text-[11px] text-amber-700 bg-amber-50 rounded-lg px-3 py-1.5">
          Take your diagnostic to unlock your study plan →
        </div>
      )}
    </Link>
  );
}
