import { useState, useMemo, useCallback } from "react";
import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { ClassCard, ClassCardSkeleton } from "../../components/ClassCard";
import { NextStepCard, EmptyNextSteps } from "./NextStepCard";
import {
  SubjectScoresSection,
  SubjectEntry,
  ResolvedSubjectScore,
} from "./SubjectScoresSection";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";

export function StudentDashboard() {
  const { logout } = useAuth();
  const {
    data: studentInfo,
    isLoading: isInfoLoading,
    isError: isInfoError,
  } = useStudentInfo();
  const { data: classesData, isLoading: isClassesLoading } = useMyClasses();
  const { data: dashboardData, isPending: isDashboardLoading } =
    useStudentDashboard();

  // Extract student info
  const firstName = studentInfo?.firstName || "";
  const lastName = studentInfo?.lastName || "";
  const studentName =
    firstName && lastName ? `${firstName} ${lastName}` : firstName || "Student";
  const gradeName = studentInfo?.gradeName || "";
  const curriculumName = studentInfo?.curriculumName || "";

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

  if (isInfoError) {
    return (
      <StudentLayout
        activeNav="home"
        studentName={studentName}
        gradeName={gradeName}
        curriculumName={curriculumName}
        onLogout={logout}
      >
        <div className="text-center py-8">
          <p className="text-brand-red">
            Failed to load dashboard data. Please try again or contact support
            if the problem persists.
          </p>
        </div>
      </StudentLayout>
    );
  }

  // For now, default empty arrays - these would come from other API calls
  const studyPlans = dashboardData?.studyPlans ?? [];
  const assessments = dashboardData?.assessments ?? [];

  const activeStudyPlans =
    studyPlans?.filter((sp) => sp.status === "ACTIVE") || [];
  const inProgressStudyPlans =
    studyPlans?.filter((sp) => sp.status === "IN_PROGRESS") || [];

  // Build next steps including subject scores for weakest-area logic
  const nextSteps = buildNextSteps(
    assessments,
    activeStudyPlans,
    inProgressStudyPlans,
    resolvedSubjectScores,
  );

  // Build unique subjects from enrolled classes for subject scores section
  const uniqueSubjects = useMemo<SubjectEntry[]>(() => {
    const seen = new Set<string>();
    const result: SubjectEntry[] = [];
    const safeClasses = Array.isArray(classesData) ? classesData : [];
    for (const cls of safeClasses) {
      if (cls.subjectId && !seen.has(cls.subjectId)) {
        seen.add(cls.subjectId);
        result.push({ subjectId: cls.subjectId, subjectName: cls.subjectName });
      }
    }
    return result;
  }, [classesData]);

  // Build class items for sidebar - safely handle potentially non-array data
  const sidebarClasses = Array.isArray(classesData)
    ? classesData.map((cls: StudentClassResponse) => ({
        id: cls.id,
        name: cls.name,
        subjectName: cls.subjectName,
        subjectId: cls.subjectId,
        diagnosticStatus: cls.onboardingDiagnosticStatus,
        diagnosticAttemptId: cls.diagnosticAttemptId,
      }))
    : [];

  return (
    <StudentLayout
      activeNav="home"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      <div className="space-y-6">
        {/* Subject Scores Section - Render first before My Classes */}
        {!isInfoLoading && uniqueSubjects.length > 0 && (
          <SubjectScoresSection
            subjects={uniqueSubjects}
            onScoresResolved={handleScoresResolved}
          />
        )}

        {/* Class Cards - Per-class diagnostic locked/unlocked state */}
        {(() => {
          const safeClasses = Array.isArray(classesData) ? classesData : [];
          if (safeClasses.length === 0) return null;
          return (
            <div>
              <h2 className="font-sans text-section-label font-bold uppercase tracking-[0.8px] text-brand-body mb-2.5">
                My classes
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {isClassesLoading
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
                        diagnosticStatus={cls.onboardingDiagnosticStatus}
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
            What's waiting for you
          </h2>
          <div className="space-y-3">
            {isInfoLoading || isClassesLoading || isDashboardLoading ? (
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
}

function buildNextSteps(
  assessments: Array<{ id: string; subjectName: string; dueDate: string }>,
  activeStudyPlans: Array<{ id: string; title: string; status: string }>,
  inProgressStudyPlans: Array<{ id: string; title: string; status: string }>,
  subjectScores: ResolvedSubjectScore[],
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
