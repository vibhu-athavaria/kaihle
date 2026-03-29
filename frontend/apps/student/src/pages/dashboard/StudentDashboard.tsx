import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { ClassCard, ClassCardSkeleton } from "../../components/ClassCard";
import { NextStepCard, EmptyNextSteps } from "./NextStepCard";
import { SubjectScoreCard } from "./SubjectScoreCard";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function StudentDashboard() {
  const { logout } = useAuth();
  const { data, isLoading, isError } = useStudentDashboard();
  const { status: onboardingStatus } = useOnboardingStatus();

  if (isError) {
    return (
      <StudentLayout activeNav="home" onLogout={logout}>
        <div className="text-center py-8">
          <p className="text-brand-red">
            Failed to load dashboard data. Please try again or contact support
            if the problem persists.
          </p>
        </div>
      </StudentLayout>
    );
  }

  const greeting = getGreeting();
  const firstName = data?.studentInfo.firstName || "";
  const gradeName = data?.studentInfo.gradeName || "";
  const curriculumName = data?.studentInfo.curriculumName || "";
  const studyPlans = data?.studyPlans || [];
  const assessments = data?.assessments || [];
  const subjects = data?.gapMap?.subjects || [];

  const activeStudyPlans = studyPlans.filter((sp) => sp.status === "ACTIVE");
  const inProgressStudyPlans = studyPlans.filter(
    (sp) => sp.status === "IN_PROGRESS",
  );

  // Get enrolled classes from onboarding status with diagnostic status
  const enrolledClasses = onboardingStatus?.diagnostics_by_class || [];
  const isClassesLoading = !onboardingStatus && !isLoading;

  const nextSteps = buildNextSteps(
    assessments,
    activeStudyPlans,
    inProgressStudyPlans,
  );

  return (
    <StudentLayout activeNav="home" onLogout={logout}>
      <div className="space-y-6">
        {/* Header with greeting */}
        <div>
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            {greeting}
            {firstName ? `, ${firstName}` : ""} 👋
          </h1>
          {gradeName && curriculumName && (
            <p className="font-sans text-sm text-brand-muted mt-1">
              {gradeName} · {curriculumName}
            </p>
          )}
        </div>

        {/* Subject Score Cards - 3 columns per spec */}
        {subjects.length > 0 && (
          <div>
            <h2 className="font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3">
              Your Performance
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {isLoading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="bg-white rounded-2xl border border-brand-border p-4 text-center animate-pulse"
                    >
                      <div className="h-8 w-16 bg-brand-border rounded mx-auto mb-2" />
                      <div className="h-3 w-12 bg-brand-border rounded mx-auto" />
                    </div>
                  ))
                : subjects
                    .slice(0, 3)
                    .map((subject) => (
                      <SubjectScoreCard
                        key={subject.subjectCode}
                        subjectName={subject.subjectName}
                        score={subject.score}
                      />
                    ))}
            </div>
          </div>
        )}

        {/* Class Cards - Per-class diagnostic locked/unlocked state */}
        {enrolledClasses.length > 0 && (
          <div>
            <h2 className="font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3">
              My Classes
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {isClassesLoading
                ? Array.from({ length: enrolledClasses.length || 2 }).map(
                    (_, i) => <ClassCardSkeleton key={i} />,
                  )
                : enrolledClasses.map((cls) => (
                    <ClassCard
                      key={cls.class_id}
                      classId={cls.class_id}
                      subjectName={cls.class_name}
                      gradeName={gradeName}
                      teacherName="Your Teacher"
                      diagnosticStatus={cls.status}
                      hasNewMessages={false}
                      hasNewProgressCheck={false}
                      topicCount={0}
                    />
                  ))}
            </div>
          </div>
        )}

        {/* What's waiting for you */}
        {nextSteps.length > 0 && (
          <div>
            <h2 className="font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3">
              What's waiting for you
            </h2>
            <div className="space-y-3">
              {isLoading
                ? Array.from({ length: 2 }).map((_, i) => (
                    <SkeletonNextStep key={i} />
                  ))
                : nextSteps
                    .slice(0, 3)
                    .map((step) => (
                      <NextStepCard
                        key={step.id}
                        type={step.type}
                        title={step.title}
                        subtitle={step.subtitle}
                        actionLabel={step.actionLabel}
                      />
                    ))}
            </div>
          </div>
        )}

        {nextSteps.length === 0 &&
          !isLoading &&
          enrolledClasses.length === 0 &&
          subjects.length === 0 && (
            <div>
              <h2 className="font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3">
                Keep going
              </h2>
              <EmptyNextSteps />
            </div>
          )}
      </div>
    </StudentLayout>
  );
}

interface NextStep {
  type:
    | "assessment"
    | "study-plan-ready"
    | "study-plan-progress"
    | "weakest-area";
  id: string;
  title: string;
  subtitle: string;
  actionLabel: string;
}

function buildNextSteps(
  assessments: Array<{ id: string; subjectName: string; dueDate: string }>,
  activeStudyPlans: Array<{ id: string; title: string; status: string }>,
  inProgressStudyPlans: Array<{ id: string; title: string; status: string }>,
): NextStep[] {
  const nextSteps: NextStep[] = [];

  // Priority 1: Active assessments due within 7 days
  if (assessments.length > 0) {
    nextSteps.push({
      type: "assessment",
      id: `assessment-${assessments[0].id}`,
      title: `${assessments.length} assessment${
        assessments.length > 1 ? "s" : ""
      } due`,
      subtitle: `${assessments[0].subjectName} · Due ${new Date(
        assessments[0].dueDate,
      ).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
      })}`,
      actionLabel: "Start now →",
    });
  }

  // Priority 2: Study plans with status ACTIVE (not yet started)
  if (activeStudyPlans.length > 0) {
    nextSteps.push({
      type: "study-plan-ready",
      id: "study-plan-ready",
      title: `${activeStudyPlans.length} study plan${
        activeStudyPlans.length > 1 ? "s" : ""
      } ready`,
      subtitle: "Start learning where it counts",
      actionLabel: "View plans →",
    });
  }

  // Priority 3: Study plans with status IN_PROGRESS (started, not finished)
  if (inProgressStudyPlans.length > 0) {
    nextSteps.push({
      type: "study-plan-progress",
      id: `study-plan-progress-${inProgressStudyPlans[0].id}`,
      title: "Continue your study plan",
      subtitle: inProgressStudyPlans[0].title,
      actionLabel: "Continue →",
    });
  }

  return nextSteps;
}

function SkeletonNextStep() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border p-4 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-brand-border rounded-full" />
        <div className="flex-1">
          <div className="h-4 w-32 bg-brand-border rounded mb-2" />
          <div className="h-3 w-24 bg-brand-border-soft rounded" />
        </div>
      </div>
    </div>
  );
}
