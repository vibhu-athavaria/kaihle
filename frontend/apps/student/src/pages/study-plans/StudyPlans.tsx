import { Link } from "react-router-dom";
import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";
import { useMyStudyPlans, type StudyPlanSummary } from "../../hooks/useMyStudyPlans";

export function StudyPlans() {
  const { logout } = useAuth();
  const { data: studentInfo } = useStudentInfo();
  const { data: classesData } = useMyClasses();
  const { data: plansData, isLoading } = useMyStudyPlans();

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  const plans = plansData?.data ?? [];

  const activePlans = plans.filter(
    (p) => p.status === "ACTIVE" || p.status === "IN_PROGRESS",
  );
  const generatingPlans = plans.filter((p) => p.status === "GENERATING");
  const completedPlans = plans.filter((p) => p.status === "COMPLETED");

  const hasDiagnosticComplete = sidebarClasses.some(
    (cls) => cls.diagnosticStatus === "COMPLETED",
  );

  return (
    <StudentLayout
      activeNav="study-plans"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      <div className="space-y-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Study Plans
        </h1>

        {isLoading ? (
          <StudyPlansLoadingSkeleton />
        ) : plans.length === 0 ? (
          <EmptyStudyPlans hasDiagnosticComplete={hasDiagnosticComplete} />
        ) : (
          <div className="space-y-8">
            {activePlans.length > 0 && (
              <section>
                <h2 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-body mb-3">
                  Ready to work on
                </h2>
                <div className="space-y-3">
                  {activePlans.map((plan) => (
                    <StudyPlanCard key={plan.id} plan={plan} />
                  ))}
                </div>
              </section>
            )}

            {generatingPlans.length > 0 && (
              <section>
                <h2 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-body mb-3">
                  Being prepared
                </h2>
                <div className="space-y-3">
                  {generatingPlans.map((plan) => (
                    <GeneratingPlanCard key={plan.id} plan={plan} />
                  ))}
                </div>
              </section>
            )}

            {completedPlans.length > 0 && (
              <section>
                <h2 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-body mb-3">
                  Completed
                </h2>
                <div className="space-y-3">
                  {completedPlans.map((plan) => (
                    <StudyPlanCard key={plan.id} plan={plan} />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </StudentLayout>
  );
}

function StudyPlanCard({ plan }: { plan: StudyPlanSummary }) {
  const watchedCount = plan.resources.filter((r) => r.is_watched).length;
  const totalResources = plan.resources.length;
  const progressPct =
    totalResources > 0 ? Math.round((watchedCount / totalResources) * 100) : 0;
  const isCompleted = plan.status === "COMPLETED";

  const statusBadge = (
    {
      ACTIVE: { label: "Ready", class: "bg-brand-green-light text-brand-green" },
      IN_PROGRESS: {
        label: "In progress",
        class: "bg-brand-amber-light text-brand-gold-dark",
      },
      COMPLETED: { label: "Completed", class: "bg-brand-light text-brand-body" },
    } as Record<string, { label: string; class: string }>
  )[plan.status] ?? { label: plan.status, class: "bg-brand-light text-brand-body" };

  return (
    <Link
      to={`/student/study-plans/${plan.id}`}
      className="block bg-white border border-role-student-border rounded-card p-4 hover:shadow-md transition-shadow focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`font-sans text-xs font-semibold px-2 py-0.5 rounded-full ${statusBadge.class}`}
            >
              {statusBadge.label}
            </span>
          </div>
          <p className="font-sans font-semibold text-sm text-brand-ink truncate">
            {plan.subtopic_name}
          </p>
          {totalResources > 0 && !isCompleted && (
            <p className="font-sans text-xs text-brand-muted mt-0.5">
              {watchedCount} of {totalResources} resources watched
            </p>
          )}
          {isCompleted && plan.quiz_score !== null && (
            <p className="font-sans text-xs text-brand-muted mt-0.5">
              Quiz score: {Math.round(plan.quiz_score * 100)}%
            </p>
          )}
        </div>
        {totalResources > 0 && !isCompleted && (
          <div className="flex-shrink-0 flex flex-col items-end gap-1">
            <span className="font-sans text-xs font-semibold text-brand-body">
              {progressPct}%
            </span>
            <div className="w-16 h-1.5 bg-brand-border-soft rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-primary rounded-full transition-all duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}
      </div>
      <div className="mt-3 font-sans text-xs font-semibold text-brand-primary">
        {isCompleted
          ? "Review →"
          : plan.status === "IN_PROGRESS"
            ? "Continue →"
            : "Start →"}
      </div>
    </Link>
  );
}

function GeneratingPlanCard({ plan }: { plan: StudyPlanSummary }) {
  return (
    <div className="bg-white border border-brand-border rounded-card p-4 opacity-70">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 border-2 border-brand-primary border-t-transparent rounded-full animate-spin flex-shrink-0" />
        <div>
          <p className="font-sans font-semibold text-sm text-brand-ink">
            {plan.subtopic_name || "Preparing your plan…"}
          </p>
          <p className="font-sans text-xs text-brand-muted">
            Being personalised for you — check back shortly
          </p>
        </div>
      </div>
    </div>
  );
}

function StudyPlansLoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-white border border-brand-border rounded-card p-4 animate-pulse"
        >
          <div className="h-3 w-16 bg-brand-border rounded-full mb-2" />
          <div className="h-4 w-48 bg-brand-border rounded-full mb-1" />
          <div className="h-3 w-32 bg-brand-border-soft rounded-full" />
        </div>
      ))}
    </div>
  );
}

function EmptyStudyPlans({
  hasDiagnosticComplete,
}: {
  hasDiagnosticComplete: boolean;
}) {
  return (
    <div className="bg-white rounded-card border border-brand-border p-12 text-center">
      <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
        {hasDiagnosticComplete
          ? "Plans are being generated"
          : "No study plans yet"}
      </h3>
      <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto mb-4">
        {hasDiagnosticComplete
          ? "Your study plans are being built from your assessment results. They'll appear here soon — in the meantime, explore your progress to see where to focus."
          : "Study plans are built automatically from your assessment results — personalised to the specific topics where you have gaps. Complete your first assessment to unlock them."}
      </p>
      <Link
        to={hasDiagnosticComplete ? "/student/my-progress" : "/student/assessments"}
        className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
      >
        {hasDiagnosticComplete
          ? "View my progress →"
          : "View your assessments →"}
      </Link>
    </div>
  );
}
