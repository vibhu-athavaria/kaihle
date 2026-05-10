import { useState, useMemo, useCallback } from "react";
import { StudentLayout } from "@kaihle/ui";
import { ClassCard, ClassCardSkeleton } from "../../components/ClassCard";
import { NextStepCard, EmptyNextSteps } from "./NextStepCard";
import {
  SubjectScoresSection,
  SubjectEntry,
  ResolvedSubjectScore,
} from "./SubjectScoresSection";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import {
  useStudentDashboard,
  type ActionItem,
} from "../../hooks/useStudentDashboard";

export function StudentDashboard() {
  const layout = useStudentLayoutProps();
  const { data: dashboardData, isPending: isDashboardLoading } =
    useStudentDashboard();

  // State for resolved subject scores (used in buildNextSteps for weakest-area)
  const [resolvedSubjectScores, setResolvedSubjectScores] = useState<
    ResolvedSubjectScore[]
  >([]);

  // Handler for subject scores resolved from SubjectScoresSection.
  // Wrapped in useCallback for stable reference — without this, every render
  // creates a new function → triggers the useEffect in SubjectScoresSection
  // on every render → sets state → re-render → repeat (ST-007).
  const handleScoresResolved = useCallback((scores: ResolvedSubjectScore[]) => {
    setResolvedSubjectScores(scores);
  }, []);

  const actionItems = dashboardData?.action_items ?? [];

  // Build next steps from action_items + subject scores for weakest-area logic
  const nextSteps = buildNextSteps(actionItems, resolvedSubjectScores);

  // Build unique subjects from enrolled classes for subject scores section
  const uniqueSubjects = useMemo<SubjectEntry[]>(() => {
    const seen = new Set<string>();
    const result: SubjectEntry[] = [];
    for (const cls of layout.sidebarClasses) {
      if (cls.subjectId && !seen.has(cls.subjectId)) {
        seen.add(cls.subjectId);
        result.push({ subjectId: cls.subjectId, subjectName: cls.subjectName });
      }
    }
    return result;
  }, [layout.sidebarClasses]);

  if (layout.isError) {
    return (
      <StudentLayout
        activeNav="home"
        studentName={layout.studentName}
        gradeName={layout.gradeName}
        curriculumName={layout.curriculumName}
        classes={layout.sidebarClasses}
        onLogout={layout.onLogout}
      >
        <div className="text-center py-16">
          <p className="font-sans text-sm text-brand-body">
            Something went wrong loading your dashboard. Please refresh the
            page.
          </p>
        </div>
      </StudentLayout>
    );
  }

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
      <div className="space-y-6">
        {/* Subject Scores Section - Render first before My Classes */}
        {!layout.isLoading && uniqueSubjects.length > 0 && (
          <SubjectScoresSection
            subjects={uniqueSubjects}
            onScoresResolved={handleScoresResolved}
          />
        )}

        {/* Streak placeholder — backend streakDays always null until implemented */}
        <div className="bg-white border border-brand-border rounded-card px-4 py-3 flex items-center gap-3">
          <span className="text-brand-muted text-lg">🔥</span>
          <div>
            <div className="font-sans font-semibold text-sm text-brand-muted">
              Daily streak — coming soon
            </div>
            <div className="font-sans text-xs text-brand-muted">
              Keep checking in daily to build your streak
            </div>
          </div>
        </div>

        {/* Class Cards - Per-class diagnostic locked/unlocked state */}
        {(() => {
          const safeClasses = layout.sidebarClasses;
          if (safeClasses.length === 0) return null;
          return (
            <div>
              <h2 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-body mb-2.5">
                My classes
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {layout.isLoading
                  ? Array.from({ length: safeClasses.length || 2 }).map(
                      (_, i) => <ClassCardSkeleton key={i} />,
                    )
                  : safeClasses.map((cls) => (
                      <ClassCard
                        key={cls.id}
                        classId={cls.id}
                        className={cls.name}
                        subjectName={cls.subjectName}
                        teacherName={cls.teacherName}
                        diagnosticStatus={cls.diagnosticStatus}
                        diagnosticAttemptId={
                          cls.diagnosticAttemptId ?? undefined
                        }
                      />
                    ))}
              </div>
            </div>
          );
        })()}

        {/* What's waiting for you - Always render, show EmptyNextSteps if no steps */}
        <div>
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-body mb-3">
            What&apos;s waiting for you
          </h2>
          <div className="space-y-3">
            {layout.isLoading || isDashboardLoading ? (
              <>
                <SkeletonNextStep />
                <SkeletonNextStep />
              </>
            ) : nextSteps.length > 0 ? (
              nextSteps
                .slice(0, 3)
                .map((step) => (
                  <NextStepCard
                    key={step.id}
                    type={step.type}
                    title={step.title}
                    subtitle={step.subtitle}
                    actionLabel={step.actionLabel}
                    route={step.route}
                    urgent={step.urgent}
                  />
                ))
            ) : (
              <EmptyNextSteps />
            )}
          </div>
        </div>
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
  route: string;
  urgent?: boolean;
}

function buildNextSteps(
  actionItems: ActionItem[],
  subjectScores: ResolvedSubjectScore[],
): NextStep[] {
  const nextSteps: NextStep[] = [];

  // Sort action items by priority (lower number = higher priority)
  const sorted = [...actionItems].sort((a, b) => a.priority - b.priority);

  // Priority 1: Assessments due
  const assessmentItems = sorted.filter((a) => a.type === "assessment_due");
  if (assessmentItems.length > 0) {
    const now = Date.now();
    const fortyEightHours = 48 * 60 * 60 * 1000;
    const urgent = assessmentItems.some(
      (a) =>
        a.due_date !== null &&
        new Date(a.due_date).getTime() - now <= fortyEightHours,
    );
    nextSteps.push({
      type: "assessment",
      id: "assessment-active",
      title: `${assessmentItems.length} assessment${assessmentItems.length !== 1 ? "s" : ""} active`,
      subtitle: "Complete your pending assessments",
      actionLabel: "Start now →",
      route: "/student/assessments",
      urgent,
    });
  }

  // Priority 2: Study plans ready (not started) or in progress
  const studyPlanReady = sorted.filter(
    (a) =>
      a.type === "study_plan_continue" && a.action_url.includes("study-plans"),
  );
  if (studyPlanReady.length > 0) {
    const first = studyPlanReady[0];
    nextSteps.push({
      type: "study-plan-ready",
      id: "study-plan-ready",
      title: "Study plan ready",
      subtitle: `${first.subject_name} — ${first.class_name}`,
      actionLabel: "Begin →",
      route: first.action_url,
    });
  }

  // Priority 3: Lesson pack ready
  const lessonPackItems = sorted.filter((a) => a.type === "lesson_pack_ready");
  if (lessonPackItems.length > 0) {
    const first = lessonPackItems[0];
    nextSteps.push({
      type: "study-plan-progress",
      id: `lesson-pack-${first.class_id}`,
      title: "Lesson pack ready",
      subtitle: `${first.subject_name} — ${first.class_name}`,
      actionLabel: "View →",
      route: first.action_url,
    });
  }

  // Priority 4: Weakest subject with no active study plan (derived from subject scores)
  const hasStudyPlanStep = nextSteps.some((s) => s.type === "study-plan-ready");
  const assessedScores = subjectScores.filter((s) => s.avgMastery !== null);
  if (assessedScores.length > 0 && !hasStudyPlanStep) {
    const weakest = assessedScores.reduce((a, b) =>
      (a.avgMastery ?? 1) < (b.avgMastery ?? 1) ? a : b,
    );
    if ((weakest.avgMastery ?? 1) < 0.7) {
      nextSteps.push({
        type: "weakest-area",
        id: `weakest-${weakest.subjectName}`,
        title: `Your weakest area: ${weakest.subjectName}`,
        subtitle: `${Math.round(
          (weakest.avgMastery ?? 0) * 100,
        )}% — keep going`,
        actionLabel: "View progress →",
        route: "/student/my-progress",
      });
    }
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
