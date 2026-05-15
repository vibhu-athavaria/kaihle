import { Link } from "react-router-dom";
import {
  getMasteryStyle,
  scoreToPercent,
  getSubjectColor,
} from "@kaihle/types";

interface ClassCardProps {
  classId: string;
  className: string;
  subjectName: string;
  gradeName: string;
  studentCount: number;
  avgMastery: number | null;
}

export function ClassCard({
  classId,
  className,
  subjectName,
  gradeName,
  studentCount,
  avgMastery,
}: ClassCardProps) {
  const { textClass, dotClass, label } = getMasteryStyle(avgMastery);
  const displayPct = scoreToPercent(avgMastery);
  const subjectColor = getSubjectColor(subjectName);

  return (
    <div className="bg-white rounded-2xl border border-brand-border hover:-translate-y-0.5 hover:shadow-card-hover transition-all flex flex-col">
      <div className="p-5 flex-1">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${subjectColor}`} />
            <span className="font-display font-semibold text-brand-ink">
              {className}
            </span>
          </div>
          <span className="px-2 py-0.5 bg-gray-100 text-xs font-medium text-brand-muted rounded-full">
            {gradeName}
          </span>
        </div>

        <div>
          <div className="text-xs text-brand-muted mb-1">
            {studentCount} student{studentCount !== 1 ? "s" : ""}
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${dotClass}`}
              aria-label={label}
              role="img"
            />
            <span className={`text-sm font-semibold ${textClass}`}>
              {displayPct}
            </span>
            <span className="text-xs text-brand-muted">{label}</span>
          </div>
        </div>
      </div>

      <div className="border-t border-brand-border px-5 py-3">
        <Link
          to={`/teacher/classes/${classId}`}
          className="flex items-center justify-center w-full bg-brand-gold text-white rounded-full py-2 text-sm font-semibold hover:bg-brand-gold-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
        >
          View Class
        </Link>
      </div>
    </div>
  );
}

export function ClassCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border p-5 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-gray-200" />
          <div className="h-5 w-24 bg-gray-200 rounded" />
        </div>
        <div className="h-5 w-12 bg-gray-200 rounded-full" />
      </div>
      <div className="mb-3">
        <div className="h-3 w-16 bg-gray-200 rounded mb-2" />
        <div className="h-4 w-20 bg-gray-200 rounded" />
      </div>
      <div className="border-t border-brand-border pt-3 flex gap-4">
        <div className="h-4 w-16 bg-gray-200 rounded" />
        <div className="h-4 w-20 bg-gray-200 rounded" />
      </div>
    </div>
  );
}
