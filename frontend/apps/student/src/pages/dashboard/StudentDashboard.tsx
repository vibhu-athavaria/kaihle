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
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
import { type AssessmentItem } from "../../hooks/useStudentAssessments";

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

  const studyPlans = dashboardData?.studyPlans ?? [];
  const activeAssessments = dashboardData?.activeAssessments ?? [];

  const activeStudyPlans =
    studyPlans?.filter((sp) => sp.status === "ACTIVE") || [];
  const inProgressStudyPlans =
    studyPlans?.filter((sp) => sp.status === "IN_PROGRESS") || [];

  // Build next steps including subject scores for weakest-area logic
  const nextSteps = buildNextSteps(
    activeAssessments,
    activeStudyPlans,
    inProgressStudyPlans,
    resolvedSubjectScores,
  );

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
  activeAssessments: AssessmentItem[],
  activeStudyPlans: Array<{ id: string; title: string; status: string }>,
  inProgressStudyPlans: Array<{ id: string; title: string; status: string }>,
  subjectScores: ResolvedSubjectScore[],
): NextStep[] {
  const nextSteps: NextStep[] = [];

  // Priority 1: Active assessments
  // urgent = any active assessment has a deadline within 48 hours
  if (activeAssessments.length > 0) {
    const now = Date.now();
    const fortyEightHours = 48 * 60 * 60 * 1000;
    const urgent = activeAssessments.some(
      (a) =>
        a.deadline !== null &&
        new Date(a.deadline).getTime() - now <= fortyEightHours,
    );
    nextSteps.push({
      type: "assessment",
      id: "assessment-active",
      title: `${activeAssessments.length} assessment${activeAssessments.length !== 1 ? "s" : ""} active`,
      subtitle: "Complete your pending assessments",
      actionLabel: "Start now →",
      route: "/student/assessments",
      urgent,
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
      actionLabel: "Begin →",
      route: "/student/study-plans",
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
      route: `/student/study-plans/${inProgressStudyPlans[0].id}`,
    });
  }

  // Priority 4: Weakest subject with no active study plan
  const assessedScores = subjectScores.filter((s) => s.avgMastery !== null);
  if (assessedScores.length > 0 && activeStudyPlans.length === 0) {
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
