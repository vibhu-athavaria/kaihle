import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@kaihle/auth";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { ClassCard, ClassCardSkeleton } from "./ClassCard";
import { ThisWeekCard } from "./ThisWeekCard";

export function TeacherDashboard() {
  const { user } = useAuth();
  const schoolId = user?.school_id || null;
  const { data, isLoading, isError } = useTeacherDashboard(schoolId);

  const needsAttention = (data?.classes ?? []).filter(
    (cls) => cls.studentsBelow > 0,
  );
  const displayedClasses = (data?.classes ?? []).slice(0, 3);
  const hasMoreClasses = (data?.classes ?? []).length > 3;

  return (
    <div className="p-6">
      {isError && (
        <div className="text-red-600 p-4 bg-red-50 rounded-lg mb-6">
          Failed to load dashboard. Please try again.
        </div>
      )}

      {/* Needs Attention — class-level alerts */}
      {needsAttention.length > 0 && (
        <div className="mb-6 space-y-3">
          {needsAttention.slice(0, 3).map((cls) => (
            <div
              key={cls.id}
              className="bg-brand-gold-light border border-brand-gold-mid rounded-xl p-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <AlertTriangle
                  className="w-5 h-5 text-brand-gold"
                  aria-hidden="true"
                />
                <span className="text-sm font-medium text-brand-ink">
                  {cls.name} ·{" "}
                  {cls.avgMastery !== null
                    ? `${Math.round(cls.avgMastery * 100)}% avg`
                    : "No data"}{" "}
                  · {cls.studentsBelow} student
                  {cls.studentsBelow !== 1 ? "s" : ""} below 40%
                </span>
              </div>
              <Link
                to={`/teacher/classes/${cls.id}/gap-map`}
                className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
              >
                Open Gap Map →
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* My Classes */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
            My classes
          </h2>
          {hasMoreClasses && (
            <Link
              to="/teacher/classes"
              className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
            >
              See all →
            </Link>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <ClassCardSkeleton key={i} />
              ))
            : displayedClasses.map((cls) => (
                <ClassCard
                  key={cls.id}
                  classId={cls.id}
                  className={cls.name}
                  subjectName={cls.subjectName}
                  gradeName={cls.gradeName}
                  studentCount={cls.studentCount}
                  avgMastery={cls.avgMastery}
                />
              ))}
        </div>
      </div>

      {/* This week */}
      <div>
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          This week
        </h2>
        <ThisWeekCard lessonPlan={data?.lessonPlan} />
      </div>
    </div>
  );
}
