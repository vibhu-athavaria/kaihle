// frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
import { ActionQueue } from "./ActionQueue";
import { ClassCard } from "./ClassCard";

function DashboardSkeleton() {
  return (
    <div
      className="space-y-6 animate-pulse"
      aria-busy="true"
      aria-label="Loading dashboard"
    >
      <div className="h-4 bg-brand-border rounded-full w-32" />
      <div className="bg-white border border-brand-border rounded-card overflow-hidden">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="flex items-center gap-3 px-4 py-3 border-b border-brand-border-soft last:border-b-0"
          >
            <div className="w-9 h-9 rounded-lg bg-brand-border flex-shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 bg-brand-border rounded-full w-40" />
              <div className="h-2.5 bg-brand-border rounded-full w-24" />
            </div>
          </div>
        ))}
      </div>
      <div className="h-4 bg-brand-border rounded-full w-24" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="bg-white border border-brand-border rounded-card p-4 space-y-3"
          >
            <div className="flex gap-3">
              <div className="w-9 h-9 rounded-lg bg-brand-border flex-shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 bg-brand-border rounded-full w-28" />
                <div className="h-2.5 bg-brand-border rounded-full w-20" />
              </div>
            </div>
            <div className="h-1.5 bg-brand-border rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function StudentDashboard() {
  const layout = useStudentLayoutProps();
  const { data, isLoading, isError } = useStudentDashboard();

  return (
    <StudentLayout
      activeNav="home"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      assessmentBadge={layout.assessmentBadge}
      onLogout={layout.onLogout}
    >
      {isLoading && <DashboardSkeleton />}

      {isError && (
        <div role="alert" className="text-center py-16 max-w-3xl">
          <p className="text-sm text-brand-body">
            Something went wrong loading your dashboard. Please refresh.
          </p>
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-[0.8px] text-brand-muted mb-2.5">
              Today's actions
            </h2>
            <ActionQueue items={data.action_items} />
          </div>

          <div>
            <h2 className="text-xs font-bold uppercase tracking-[0.8px] text-brand-muted mb-2.5">
              My classes
            </h2>
            {data.classes.length === 0 ? (
              <div
                role="status"
                className="bg-white border border-brand-border rounded-card px-4 py-10 text-center"
              >
                <p className="text-sm font-semibold text-brand-body">
                  You're not enrolled in any classes yet.
                </p>
                <p className="text-xs text-brand-muted mt-1">
                  Ask your teacher to add you to a class.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {data.classes.map((cls) => (
                  <ClassCard key={cls.class_id} data={cls} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </StudentLayout>
  );
}
