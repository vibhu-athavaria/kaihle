import { Link, useNavigate } from "react-router-dom";
import {
  ClipboardList,
  Clock,
  CheckCircle2,
  Circle,
  type LucideIcon,
} from "lucide-react";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import {
  useStudentAssessments,
  type AssessmentItem,
  type AttemptStatus,
} from "../../hooks/useStudentAssessments";
import { useStartAssessment } from "../../hooks/useAttempt";

// ── Helpers ──────────────────────────────────────────────────

function formatDeadline(deadline: string | null): string {
  if (!deadline) return "No deadline";
  return new Date(deadline).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// ── Due-date chip ─────────────────────────────────────────────

function DueChip({ deadline }: { deadline: string | null }) {
  if (!deadline) return null;
  const due = new Date(deadline);
  const diffDays = Math.floor((due.getTime() - Date.now()) / 86_400_000);
  const label =
    diffDays <= 0
      ? "Due today"
      : diffDays === 1
        ? "Due tomorrow"
        : `Due ${due.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
  const colorClass =
    diffDays <= 0
      ? "bg-red-100 text-red-700"
      : diffDays <= 7
        ? "bg-amber-100 text-amber-800"
        : "bg-gray-100 text-[#9ca3af]";
  return (
    <span
      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${colorClass}`}
    >
      {label}
    </span>
  );
}

// ── Status badge ─────────────────────────────────────────────

interface StatusBadgeProps {
  status: AttemptStatus;
}

function StatusBadge({ status }: StatusBadgeProps) {
  const config: Record<
    AttemptStatus,
    { label: string; className: string; Icon: LucideIcon }
  > = {
    NOT_STARTED: {
      label: "Not started",
      className: "bg-gray-100 text-brand-body",
      Icon: Circle,
    },
    IN_PROGRESS: {
      label: "In progress",
      className: "bg-brand-amber-light text-brand-amber",
      Icon: Clock,
    },
    COMPLETED: {
      label: "Completed",
      className: "bg-brand-green-light text-brand-green",
      Icon: CheckCircle2,
    },
  };
  const { label, className, Icon } = config[status];
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${className}`}
    >
      <Icon className="w-3 h-3" aria-hidden={true} />
      {label}
    </span>
  );
}

// ── Teacher assessment card ───────────────────────────────────

interface TeacherAssessmentCardProps {
  assessment: AssessmentItem;
  className: string;
}

function TeacherAssessmentCard({
  assessment,
  className: classLabel,
}: TeacherAssessmentCardProps) {
  const navigate = useNavigate();
  const startAssessment = useStartAssessment();

  const existingRoute = assessment.attemptId
    ? assessment.attemptStatus === "COMPLETED"
      ? `/student/assessments/${assessment.attemptId}/results`
      : `/student/assessments/${assessment.attemptId}/take`
    : null;

  const handleStart = async () => {
    try {
      const attempt = await startAssessment.mutateAsync(assessment.id);
      navigate(`/student/assessments/${attempt.id}/take`);
    } catch {
      // error is handled by React Query's onError / isError state on startAssessment
    }
  };

  return (
    <div className="bg-white rounded-xl border border-role-student-border p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-wide text-brand-muted mb-1">
            {classLabel}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-display font-bold text-lg text-brand-ink leading-snug">
              {assessment.title}
            </h3>
            <DueChip deadline={assessment.deadline} />
          </div>
        </div>
        <StatusBadge status={assessment.attemptStatus} />
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 font-sans text-sm text-brand-body">
          <span>{assessment.questionCount} questions</span>
          <span aria-hidden="true">·</span>
          <span>{formatDeadline(assessment.deadline)}</span>
          {assessment.attemptStatus === "COMPLETED" &&
            assessment.score !== null && (
              <>
                <span aria-hidden="true">·</span>
                <span className="font-semibold text-brand-green">
                  {Math.round(assessment.score * 100)}%
                </span>
              </>
            )}
        </div>

        {existingRoute ? (
          <Link
            to={existingRoute}
            className="flex-shrink-0 bg-brand-primary text-white font-sans text-sm font-semibold px-4 py-2 rounded-full hover:opacity-90 transition-opacity focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            {assessment.attemptStatus === "COMPLETED"
              ? "View results"
              : "Continue"}
          </Link>
        ) : (
          <button
            type="button"
            onClick={handleStart}
            disabled={startAssessment.isPending}
            className="flex-shrink-0 bg-brand-primary text-white font-sans text-sm font-semibold px-4 py-2 rounded-full hover:opacity-90 transition-opacity focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-60"
          >
            {startAssessment.isPending ? "Starting…" : "Start"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Pending diagnostic card (amber) ──────────────────────────

interface PendingDiagnosticCardProps {
  assessment: AssessmentItem;
  className: string;
}

function PendingDiagnosticCard({
  assessment,
  className: classLabel,
}: PendingDiagnosticCardProps) {
  const attemptRoute = assessment.attemptId
    ? assessment.attemptStatus === "IN_PROGRESS"
      ? `/student/assessments/${assessment.attemptId}/take`
      : `/student/assessments/${assessment.attemptId}/take`
    : `/student/classes/${assessment.classId}/diagnostic`;

  const buttonLabel =
    assessment.attemptStatus === "IN_PROGRESS"
      ? "Continue →"
      : "Take diagnostic →";

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3">
      <span className="text-2xl flex-shrink-0 mt-0.5" aria-hidden="true">
        🎯
      </span>
      <div className="flex-1">
        <p className="font-sans text-[10px] font-bold uppercase tracking-wide text-amber-700 mb-0.5">
          {classLabel}
        </p>
        <div className="text-[13px] font-bold text-[#1a2016]">
          {assessment.title}
        </div>
        <div className="text-[12px] text-[#4a5240] mt-1 leading-relaxed">
          This diagnostic helps Kaihle understand your current level. Completing
          it will unlock your personalised study plan for this subject.
        </div>
        <Link
          to={attemptRoute}
          className="inline-block mt-3 font-sans text-sm font-semibold text-amber-800 hover:text-amber-900 focus-visible:ring-2 focus-visible:ring-amber-700 rounded"
        >
          {buttonLabel}
        </Link>
      </div>
    </div>
  );
}

// ── Completed diagnostic row ──────────────────────────────────

interface CompletedDiagnosticRowProps {
  assessment: AssessmentItem;
  className: string;
}

function CompletedDiagnosticRow({
  assessment,
  className: classLabel,
}: CompletedDiagnosticRowProps) {
  const resultsRoute = assessment.attemptId
    ? `/student/assessments/${assessment.attemptId}/results`
    : null;

  return (
    <div className="bg-white rounded-xl border border-role-student-border p-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-brand-green-light flex items-center justify-center flex-shrink-0">
          <ClipboardList
            className="w-4 h-4 text-brand-primary"
            aria-hidden={true}
          />
        </div>
        <div>
          <p className="font-sans text-[10px] font-bold uppercase tracking-wide text-brand-muted mb-0.5">
            {classLabel} · Diagnostic
          </p>
          <h3 className="font-display font-bold text-sm text-brand-ink">
            {assessment.title}
          </h3>
          {assessment.score !== null && (
            <p className="font-sans text-xs text-brand-body mt-0.5">
              Score:{" "}
              <span className="font-semibold text-brand-green">
                {Math.round(assessment.score * 100)}%
              </span>
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <StatusBadge status="COMPLETED" />
        {resultsRoute && (
          <Link
            to={resultsRoute}
            className="font-sans text-sm font-semibold text-brand-primary hover:opacity-80 focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
          >
            View results
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────

export function Assessments() {
  const layout = useStudentLayoutProps();

  const classMap = new Map<string, string>(
    layout.sidebarClasses.map((c) => [c.id, c.name]),
  );

  const { diagnostics, teacherAssessments, isPending, isError } =
    useStudentAssessments(
      layout.sidebarClasses.map((c) => c.id),
      layout.studentId,
    );

  const isPageLoading = layout.isLoading || isPending;

  // Split diagnostics
  const pendingDiagnostics = diagnostics.filter(
    (d) => d.attemptStatus !== "COMPLETED",
  );
  const completedDiagnostics = diagnostics.filter(
    (d) => d.attemptStatus === "COMPLETED",
  );

  // Split teacher assessments — sort upcoming by deadline (nulls last)
  const upcomingTeacher = teacherAssessments
    .filter((a) => a.attemptStatus !== "COMPLETED")
    .sort((a, b) => {
      if (!a.deadline && !b.deadline) return 0;
      if (!a.deadline) return 1;
      if (!b.deadline) return -1;
      return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
    });

  const completedTeacher = teacherAssessments.filter(
    (a) => a.attemptStatus === "COMPLETED",
  );

  const hasAnything =
    pendingDiagnostics.length > 0 ||
    completedDiagnostics.length > 0 ||
    upcomingTeacher.length > 0 ||
    completedTeacher.length > 0;

  return (
    <StudentLayout
      activeNav="assessments"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      onLogout={layout.onLogout}
      assessmentBadge={layout.assessmentBadge}
    >
      <div className="space-y-8">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Assessments
        </h1>

        {/* Loading skeleton */}
        {isPageLoading && (
          <div
            className="animate-pulse space-y-3"
            aria-label="Loading assessments"
          >
            <div className="h-20 bg-brand-border rounded-xl w-full" />
            <div className="h-20 bg-brand-border rounded-xl w-full" />
            <div className="h-20 bg-brand-border rounded-xl w-full" />
          </div>
        )}

        {/* Error state */}
        {!isPageLoading && isError && (
          <div
            role="alert"
            className="bg-red-50 border border-red-200 rounded-xl p-6 text-center"
          >
            <p className="font-sans text-sm text-red-700 font-semibold">
              Could not load assessments. Please refresh the page.
            </p>
          </div>
        )}

        {!isPageLoading && !isError && (
          <>
            {/* 1 — Teacher assessments (upcoming) */}
            {upcomingTeacher.length > 0 && (
              <section aria-labelledby="teacher-assessments-heading">
                <h2
                  id="teacher-assessments-heading"
                  className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
                >
                  Set by your teacher
                </h2>
                <div className="space-y-3">
                  {upcomingTeacher.map((a) => (
                    <TeacherAssessmentCard
                      key={a.id}
                      assessment={a}
                      className={classMap.get(a.classId) ?? "Class"}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* 2 — Diagnostic assessments */}
            {(pendingDiagnostics.length > 0 ||
              completedDiagnostics.length > 0) && (
              <section aria-labelledby="diagnostics-heading">
                <h2
                  id="diagnostics-heading"
                  className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
                >
                  Diagnostic assessments
                </h2>
                <div className="space-y-3">
                  {pendingDiagnostics.map((d) => (
                    <PendingDiagnosticCard
                      key={d.id}
                      assessment={d}
                      className={classMap.get(d.classId) ?? "Class"}
                    />
                  ))}
                  {completedDiagnostics.map((d) => (
                    <CompletedDiagnosticRow
                      key={d.id}
                      assessment={d}
                      className={classMap.get(d.classId) ?? "Class"}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* 3 — Completed teacher assessments */}
            {completedTeacher.length > 0 && (
              <section aria-labelledby="completed-heading">
                <h2
                  id="completed-heading"
                  className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
                >
                  Completed
                </h2>
                <div className="space-y-3">
                  {completedTeacher.map((a) => (
                    <TeacherAssessmentCard
                      key={a.id}
                      assessment={a}
                      className={classMap.get(a.classId) ?? "Class"}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Empty state — nothing at all */}
            {!hasAnything && (
              <div
                role="status"
                className="bg-white rounded-xl border border-role-student-border p-12 text-center"
              >
                <div className="text-4xl mb-4">📋</div>
                <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
                  No assessments yet
                </h3>
                <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto mb-4">
                  Your teacher will assign assessments here when ready.
                </p>
                <Link
                  to="/student/my-progress"
                  className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
                >
                  See your progress so far →
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </StudentLayout>
  );
}
