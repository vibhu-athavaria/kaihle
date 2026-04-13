import { useAuth } from "@kaihle/auth";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { ClassCard, ClassCardSkeleton } from "./ClassCard";
import { PendingActionBanner } from "./PendingActionBanner";
import { ThisWeekCard } from "./ThisWeekCard";

export function TeacherDashboard() {
  const { user } = useAuth();
  const schoolId = user?.school_id || null;
  const { data, isLoading, isError } = useTeacherDashboard(schoolId);

  return (
    <div className="p-6">
      {isError && (
        <div className="text-red-600 p-4 bg-red-50 rounded-lg">
          Failed to load dashboard. Please try again.
        </div>
      )}

      {data?.pendingActions && data.pendingActions.length > 0 && (
        <div className="mb-6 space-y-3">
          {data.pendingActions.slice(0, 3).map((action, i) => (
            <PendingActionBanner key={i} action={action} />
          ))}
        </div>
      )}

      <div className="mb-6">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          My classes
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <ClassCardSkeleton key={i} />
              ))
            : data?.classes.map((cls) => (
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

      <div>
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          This week
        </h2>
        <ThisWeekCard lessonPlan={data?.lessonPlan} />
      </div>
    </div>
  );
}
