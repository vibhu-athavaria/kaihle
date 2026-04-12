import { Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
import { ClassCardSkeleton } from "../dashboard/ClassCard";

const subjectColorMap: Record<string, string> = {
  Mathematics: "bg-brand-primary",
  "Integrated Science": "bg-violet-600",
  Biology: "bg-green-600",
  Chemistry: "bg-amber-600",
  Physics: "bg-blue-600",
  "English Language": "bg-red-600",
  "English Literature": "bg-purple-600",
  default: "bg-brand-muted",
};

function getSubjectColor(subjectName: string): string {
  return subjectColorMap[subjectName] || subjectColorMap.default;
}

export function ClassesPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data, isLoading } = useTeacherDashboard(schoolId);

  if (isLoading) {
    return (
      <div className="p-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
          Classes
        </h1>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <ClassCardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (!data?.classes || data.classes.length === 0) {
    return (
      <div className="p-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
          Classes
        </h1>
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-3">📚</div>
          <h3 className="font-display font-semibold text-brand-ink mb-1">
            No classes yet
          </h3>
          <p className="text-sm text-brand-muted">
            Classes will appear here once your school admin creates them.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
        Classes
      </h1>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.classes.map((cls) => {
          const { textClass, dotClass, label } = getMasteryStyle(cls.avgMastery);
          const displayPct = scoreToPercent(cls.avgMastery);
          const subjectColor = getSubjectColor(cls.subjectName);

          return (
            <div
              key={cls.id}
              className="bg-white rounded-2xl border border-brand-border p-5 hover:-translate-y-0.5 hover:shadow-card-hover transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${subjectColor}`} />
                  <span className="font-display font-semibold text-brand-ink">
                    {cls.name}
                  </span>
                </div>
                <span className="px-2 py-0.5 bg-gray-100 text-xs font-medium text-brand-muted rounded-full">
                  {cls.gradeName}
                </span>
              </div>

              <div className="mb-3">
                <div className="text-xs text-brand-muted mb-1">
                  {cls.studentCount} student{cls.studentCount !== 1 ? "s" : ""}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${dotClass}`} />
                  <span className={`text-sm font-semibold ${textClass}`}>
                    {displayPct}
                  </span>
                  <span className="text-xs text-brand-muted">{label}</span>
                </div>
              </div>

              <div className="border-t border-brand-border pt-3">
                <div className="flex gap-3 mb-2">
                  <Link
                    to={`/teacher/classes/${cls.id}/gap-map`}
                    className="text-sm font-medium text-brand-muted hover:text-brand-primary transition-colors"
                  >
                    Gap Map
                  </Link>
                  <span className="text-brand-muted">·</span>
                  <Link
                    to={`/teacher/classes/${cls.id}/assessments`}
                    className="text-sm font-medium text-brand-muted hover:text-brand-primary transition-colors"
                  >
                    Assessments
                  </Link>
                  <span className="text-brand-muted">·</span>
                  <Link
                    to={`/teacher/classes/${cls.id}/study-plan`}
                    className="text-sm font-medium text-brand-muted hover:text-brand-primary transition-colors"
                  >
                    Study Plan
                  </Link>
                </div>
                <div className="flex items-center justify-between">
                  <Link
                    to={`/teacher/classes/${cls.id}/lesson-plans`}
                    className="text-sm font-medium text-brand-muted hover:text-brand-primary transition-colors"
                  >
                    Lesson Plans
                  </Link>
                  <Link
                    to={`/teacher/classes/${cls.id}`}
                    className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark"
                  >
                    View →
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
