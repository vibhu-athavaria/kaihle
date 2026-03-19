import { Link } from "react-router-dom";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

interface ClassCardProps {
  classId: string;
  className: string;
  subjectName: string;
  gradeName: string;
  studentCount: number;
  avgMastery: number | null;
}

const subjectColorMap: Record<string, string> = {
  Mathematics: "bg-brand-blue",
  Science: "bg-brand-green",
  English: "bg-brand-amber",
  History: "bg-brand-red",
  Art: "bg-brand-purple",
  Music: "bg-brand-pink",
  default: "bg-brand-muted",
};

function getSubjectColor(subjectName: string): string {
  return subjectColorMap[subjectName] || subjectColorMap.default;
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
    <div className="bg-white rounded-2xl border border-role-teacher-border p-5 hover:-translate-y-0.5 hover:shadow-card-hover transition-all">
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

      <div className="mb-3">
        <div className="text-xs text-role-teacher-muted mb-1">
          {studentCount} student{studentCount !== 1 ? "s" : ""}
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${dotClass}`} />
          <span className={`text-sm font-semibold ${textClass}`}>
            {displayPct}
          </span>
          <span className="text-xs text-brand-muted">{label}</span>
        </div>
      </div>

      <div className="border-t border-brand-border pt-3 flex gap-4">
        <Link
          to={`/teacher/classes/${classId}/gap-map`}
          className="text-sm font-semibold text-brand-body hover:text-brand-primary"
        >
          Gap Map →
        </Link>
        <Link
          to={`/teacher/classes/${classId}/assessments`}
          className="text-sm font-semibold text-brand-body hover:text-brand-primary"
        >
          Assessment →
        </Link>
      </div>
    </div>
  );
}

export function ClassCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-role-teacher-border p-5 animate-pulse">
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
