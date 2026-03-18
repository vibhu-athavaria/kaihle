import { DashboardLayout } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { Plus } from "lucide-react";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { ClassCard, ClassCardSkeleton } from "./ClassCard";
import { PendingActionBanner } from "./PendingActionBanner";
import { ThisWeekCard } from "./ThisWeekCard";
import { Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";

export function TeacherDashboard() {
  const { user } = useAuth();
  const schoolId = user?.school_id || null;
  const { data, isLoading, isError } = useTeacherDashboard(schoolId);

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

  return (
    <DashboardLayout
      variant="teacher"
      pageTitle={`${greeting()}, ${teacherName}`}
      topNavAction={
        <Link to="/teacher/assessments/new">
          <Button
            variant="primary"
            size="sm"
            className="gap-1 bg-brand-gold hover:bg-brand-gold-dark"
          >
            <Plus className="w-4 h-4" />
            Assessment
          </Button>
        </Link>
      }
    >
      {isError && (
        <div className="text-red-600 p-4 bg-red-50 rounded-lg">
          Failed to load dashboard. Please try again.
        </div>
      )}

      {data.pendingActions.length > 0 && (
        <div className="mb-6">
          <PendingActionBanner action={data.pendingActions[0]} />
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
            : data.classes.map((cls) => (
                <ClassCard
                  key={cls.id}
                  classId={cls.id}
                  className={cls.name}
                  subjectName={cls.subjectName}
                  gradeName={cls.gradeName}
                  studentCount={cls.studentCount}
                  avgMastery={cls.avgMastery}
                  lessonPlanStatus={cls.lessonPlanStatus}
                />
              ))}
        </div>
      </div>

      <div>
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          This week
        </h2>
        <ThisWeekCard lessonPlan={data.lessonPlan} />
      </div>
    </DashboardLayout>
  );
}
