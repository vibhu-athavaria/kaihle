import { StudentShellLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { ClassCard, ClassCardSkeleton } from "../../components/ClassCard";
import { NextStepCard, EmptyNextSteps } from "./NextStepCard";
import { SubjectScoreCard } from "./SubjectScoreCard";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";
import { useNavigate } from "react-router-dom";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function getInitials(name: string): string {
  const parts = name?.split(" ") || [];
  if (parts.length >= 2) {
    return (parts[0]?.charAt(0) || "") + (parts[1]?.charAt(0) || "");
  }
  return name?.charAt(0) || "";
}

export function StudentDashboard() {
  const { logout } = useAuth();
  const { data, isLoading, isError } = useStudentDashboard();
  const { status: onboardingStatus } = useOnboardingStatus();
  const navigate = useNavigate();

  if (isError) {
    return (
      <StudentShellLayout
        activeNav="home"
        onLogout={logout}
        onNavClick={(nav) => {
          if (nav === "home") navigate("/student/dashboard");
          else if (nav === "progress") navigate("/student/my-progress");
          else if (nav === "study") navigate("/student/study-plans");
          else if (nav === "assessments") navigate("/student/assessments");
        }}
      >
        <div className="text-center py-8">
          <p className="text-brand-red">
            Failed to load dashboard data. Please try again or contact support
            if the problem persists.
          </p>
        </div>
      </StudentShellLayout>
    );
  }

  const greeting = getGreeting();
  const firstName = data?.studentInfo.firstName || "";
  const fullName = data?.studentInfo.firstName || "";
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

  // Build class items for sidebar
  const sidebarClasses = enrolledClasses.map((cls) => ({
    id: cls.class_id,
    name: cls.class_name,
    isLocked: cls.status === "PENDING" || cls.status === "IN_PROGRESS",
  }));

  // Build header content
  const headerContent = (
    <div>
      <div className="font-sans text-sm font-medium text-brand-ink">
        {greeting}
        {firstName ? `, ${firstName}` : ""} 👋
      </div>
      {gradeName && curriculumName && (
        <div className="font-sans text-[10px] text-brand-muted">
          {gradeName} · {curriculumName}
        </div>
      )}
    </div>
  );

  return (
    <StudentShellLayout
      activeNav="home"
      headerContent={headerContent}
      studentName={fullName || "Student"}
      studentInitials={getInitials(fullName)}
      gradeInfo={
        gradeName ? `${gradeName} · ${curriculumName}` : curriculumName
      }
      classes={sidebarClasses}
      onLogout={logout}
      onNavClick={(nav) => {
        if (nav === "home") navigate("/student/dashboard");
        else if (nav === "progress") navigate("/student/my-progress");
        else if (nav === "study") navigate("/student/study-plans");
        else if (nav === "assessments") navigate("/student/assessments");
      }}
      onClassClick={(classId) => {
        const cls = enrolledClasses.find((c) => c.class_id === classId);
        if (cls && (cls.status === "PENDING" || cls.status === "IN_PROGRESS")) {
          navigate(`/student/classes/${classId}/diagnostic`);
        } else {
          navigate(`/student/classes/${classId}/topics`);
        }
      }}
    >
      <div className="space-y-6">
        {/* Subject Score Cards - 3 columns per spec */}
        {subjects.length > 0 && (
          <div>
            <h2 className="font-sans text-[9px] font-bold uppercase tracking-widest text-brand-muted mb-3">
              Your subjects
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {isLoading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="bg-white rounded-xl border border-brand-border p-3 text-center animate-pulse"
                    >
                      <div className="h-6 w-12 bg-brand-border rounded mx-auto mb-1" />
                      <div className="h-2 w-10 bg-brand-border rounded mx-auto" />
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
            <h2 className="font-sans text-[9px] font-bold uppercase tracking-widest text-brand-muted mb-3">
              My classes
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
            <h2 className="font-sans text-[9px] font-bold uppercase tracking-widest text-brand-muted mb-3">
              What's waiting for you
            </h2>
            <div className="space-y-2">
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
              <h2 className="font-sans text-[9px] font-bold uppercase tracking-widest text-brand-muted mb-3">
                Keep going
              </h2>
              <EmptyNextSteps />
            </div>
          )}
      </div>
    </StudentShellLayout>
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
    <div className="bg-white rounded-xl border border-brand-border p-3 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-brand-border rounded-full" />
          <div>
            <div className="h-3 w-32 bg-brand-border rounded mb-1" />
            <div className="h-2 w-20 bg-brand-border-soft rounded" />
          </div>
        </div>
        <div className="h-3 w-16 bg-brand-border rounded" />
      </div>
    </div>
  );
}
