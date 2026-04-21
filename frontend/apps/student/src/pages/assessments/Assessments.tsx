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
    const attempt = await startAssessment.mutateAsync(assessment.id);
    navigate(`/student/assessments/${attempt.id}/take`);
  };

  return (
    <div className="bg-white rounded-xl border border-role-student-border p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-wide text-brand-muted mb-1">
            {classLabel}
          </p>
          <h3 className="font-display font-bold text-lg text-brand-ink leading-snug">
            {assessment.title}
          </h3>
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

// ── Diagnostic card ───────────────────────────────────────────

interface DiagnosticCardProps {
  assessment: AssessmentItem;
  className: string;
}

function DiagnosticCard({
  assessment,
  className: classLabel,
}: DiagnosticCardProps) {
  const isCompleted = assessment.attemptStatus === "COMPLETED";
  const attemptRoute = assessment.attemptId
    ? isCompleted
      ? `/student/assessments/${assessment.attemptId}/results`
      : `/student/assessments/${assessment.attemptId}/take`
    : `/student/classes/${assessment.classId}/diagnostic`;

  const buttonLabel =
    assessment.attemptStatus === "IN_PROGRESS"
      ? "Continue"
      : isCompleted
        ? "View results"
        : "Start";

  return (
    <div className="bg-white rounded-xl border border-role-student-border p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-brand-green-light flex items-center justify-center flex-shrink-0">
          <ClipboardList
            className="w-5 h-5 text-brand-primary"
            aria-hidden={true}
          />
        </div>
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-wide text-brand-muted mb-0.5">
            {classLabel} · Get started
          </p>
          <h3 className="font-display font-bold text-base text-brand-ink">
            {assessment.title}
          </h3>
          <p className="font-sans text-xs text-brand-body mt-0.5">
            {assessment.questionCount} questions · Unlocks class content
          </p>
        </div>
      </div>

      {attemptRoute && (
        <Link
          to={attemptRoute}
          className="flex-shrink-0 bg-brand-primary text-white font-sans text-sm font-semibold px-4 py-2 rounded-full hover:opacity-90 transition-opacity focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {buttonLabel}
        </Link>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────

export function Assessments() {
  const layout = useStudentLayoutProps();

  const classMap = new Map<string, string>(
    layout.sidebarClasses.map((c) => [c.id, c.name]),
  );

  const { diagnostics, teacherAssessments, isPending } = useStudentAssessments(
    layout.sidebarClasses.map((c) => c.id),
    layout.studentId,
  );

  const isPageLoading = layout.isLoading || isPending;

  const pendingDiagnostics = diagnostics.filter(
    (d) => d.attemptStatus !== "COMPLETED",
  );

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
          </div>
        )}

        {!isPageLoading && (
          <>
            {/* Get Started — pending diagnostics */}
            {pendingDiagnostics.length > 0 && (
              <section aria-labelledby="get-started-heading">
                <h2
                  id="get-started-heading"
                  className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
                >
                  Get Started
                </h2>
                <div className="space-y-3">
                  {pendingDiagnostics.map((d) => (
                    <DiagnosticCard
                      key={d.id}
                      assessment={d}
                      className={classMap.get(d.classId) ?? "Class"}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Teacher assessments */}
            <section aria-labelledby="teacher-assessments-heading">
              <h2
                id="teacher-assessments-heading"
                className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
              >
                Assigned by teacher
              </h2>

              {teacherAssessments.length === 0 ? (
                <div className="bg-white rounded-xl border border-role-student-border p-12 text-center">
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
              ) : (
                <div className="space-y-3">
                  {teacherAssessments.map((a) => (
                    <TeacherAssessmentCard
                      key={a.id}
                      assessment={a}
                      className={classMap.get(a.classId) ?? "Class"}
                    />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </StudentLayout>
  );
}
