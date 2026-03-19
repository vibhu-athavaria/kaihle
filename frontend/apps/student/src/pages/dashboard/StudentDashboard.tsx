import { SubjectScoreCard } from "./SubjectScoreCard";
import { NextStepCard, EmptyNextSteps } from "./NextStepCard";
import { StreakBadge } from "./StreakBadge";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border p-4 text-center animate-pulse">
      <div className="h-8 w-16 bg-brand-border rounded mx-auto mb-2" />
      <div className="h-3 w-20 bg-brand-border-soft rounded mx-auto" />
      <div className="h-2 w-12 bg-brand-border-soft rounded mx-auto mt-1" />
    </div>
  );
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

interface NextStep {
  type:
    | "assessment"
    | "study-plan-ready"
    | "study-plan-progress"
    | "weakest-area";
  title: string;
  subtitle: string;
  actionLabel: string;
}

export function StudentDashboard() {
  const { data, isLoading, isError } = useStudentDashboard();

  if (isError) {
    return (
      <div className="p-6">
        <div className="text-center py-8">
          <p className="text-brand-red">Failed to load dashboard data.</p>
        </div>
      </div>
    );
  }

  const greeting = getGreeting();
  const firstName = data?.studentInfo.firstName || "";
  const gradeName = data?.studentInfo.gradeName || "";
  const curriculumName = data?.studentInfo.curriculumName || "";
  const streakDays = data?.studentInfo.streakDays || 0;
  const subjects = data?.gapMap.subjects || [];
  const studyPlans = data?.studyPlans || [];
  const assessments = data?.assessments || [];

  const activeStudyPlans = studyPlans.filter((sp) => sp.status === "ACTIVE");
  const inProgressStudyPlans = studyPlans.filter(
    (sp) => sp.status === "IN_PROGRESS",
  );

  const weakestSubject =
    subjects.length > 0
      ? subjects.reduce(
          (weakest, current) =>
            current.score !== null &&
            (weakest.score === null || current.score < weakest.score)
              ? current
              : weakest,
          subjects[0],
        )
      : null;

  const nextSteps: NextStep[] = [];

  if (assessments.length > 0) {
    nextSteps.push({
      type: "assessment",
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

  if (activeStudyPlans.length > 0) {
    nextSteps.push({
      type: "study-plan-ready",
      title: `${activeStudyPlans.length} study plan${
        activeStudyPlans.length > 1 ? "s" : ""
      } ready`,
      subtitle: "Start learning where it counts",
      actionLabel: "View plans →",
    });
  }

  if (inProgressStudyPlans.length > 0) {
    nextSteps.push({
      type: "study-plan-progress",
      title: "Continue your study plan",
      subtitle: inProgressStudyPlans[0].title,
      actionLabel: "Continue →",
    });
  }

  if (
    weakestSubject &&
    weakestSubject.score !== null &&
    weakestSubject.score < 0.4
  ) {
    nextSteps.push({
      type: "weakest-area",
      title: `Your weakest area: ${weakestSubject.subjectName}`,
      subtitle: `${Math.round(weakestSubject.score * 100)}%`,
      actionLabel: "See what to work on →",
    });
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            {greeting}
            {firstName ? `, ${firstName}` : ""} 👋
          </h1>
          <StreakBadge days={streakDays} />
        </div>
        {gradeName && curriculumName && (
          <p className="font-sans text-sm text-brand-muted mt-1">
            {gradeName} · {curriculumName}
          </p>
        )}
      </div>

      <div>
        <div className="grid grid-cols-3 gap-3">
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            : subjects
                .slice(0, 3)
                .map((subject) => (
                  <SubjectScoreCard
                    key={subject.subjectCode}
                    subjectName={subject.subjectName}
                    subjectCode={subject.subjectCode}
                    score={subject.score}
                  />
                ))}
        </div>
      </div>

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
                  .map((step, index) => (
                    <NextStepCard
                      key={index}
                      type={step.type}
                      title={step.title}
                      subtitle={step.subtitle}
                      actionLabel={step.actionLabel}
                    />
                  ))}
          </div>
        </div>
      )}

      {nextSteps.length === 0 && !isLoading && (
        <div>
          <h2 className="font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3">
            Keep going
          </h2>
          <EmptyNextSteps />
        </div>
      )}
    </div>
  );
}
