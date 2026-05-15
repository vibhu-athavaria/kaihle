import { useNavigate } from "react-router-dom";
import {
  Clock,
  CheckCircle2,
  Circle,
  ClipboardList,
  type LucideIcon,
} from "lucide-react";
import { getMasteryStyle } from "@kaihle/types";
import {
  useMyAssessments,
  type AttemptStatus,
  type MyAssessmentItem,
} from "../../../hooks/useMyAssessments";
import { useStartAssessment } from "../../../hooks/useAttempt";

interface AssessmentsTabProps {
  classId: string;
}

function formatDeadline(deadline: string | null): string {
  if (!deadline) return "";
  return new Date(deadline).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

function DueChip({ deadline }: { deadline: string | null }) {
  if (!deadline) return null;
  const diffDays = Math.floor(
    (new Date(deadline).getTime() - Date.now()) / 86_400_000,
  );
  const label =
    diffDays <= 0
      ? "Due today"
      : diffDays === 1
        ? "Due tomorrow"
        : `Due ${formatDeadline(deadline)}`;
  const colorClass =
    diffDays <= 0
      ? "bg-red-100 text-red-700"
      : diffDays <= 7
        ? "bg-amber-100 text-amber-800"
        : "bg-gray-100 text-brand-muted";
  return (
    <span
      className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${colorClass}`}
    >
      {label}
    </span>
  );
}

function StatusBadge({ status }: { status: AttemptStatus }) {
  const config: Record<
    AttemptStatus,
    { label: string; cls: string; Icon: LucideIcon }
  > = {
    NOT_STARTED: {
      label: "Not started",
      cls: "bg-gray-100 text-brand-body",
      Icon: Circle,
    },
    IN_PROGRESS: {
      label: "In progress",
      cls: "bg-brand-amber-light text-brand-amber",
      Icon: Clock,
    },
    COMPLETED: {
      label: "Completed",
      cls: "bg-brand-green-light text-brand-green",
      Icon: CheckCircle2,
    },
  };
  const { label, cls, Icon } = config[status];
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}
    >
      <Icon className="w-3 h-3" aria-hidden="true" />
      {label}
    </span>
  );
}

function AssessmentCard({ assessment }: { assessment: MyAssessmentItem }) {
  const navigate = useNavigate();
  const startAssessment = useStartAssessment();

  const handleAction = async () => {
    if (assessment.attemptStatus === "COMPLETED" && assessment.attemptId) {
      navigate(`/student/assessments/${assessment.attemptId}/results`);
    } else if (
      assessment.attemptStatus === "IN_PROGRESS" &&
      assessment.attemptId
    ) {
      navigate(`/student/assessments/${assessment.attemptId}/take`);
    } else {
      try {
        const attempt = await startAssessment.mutateAsync(assessment.id);
        navigate(`/student/assessments/${attempt.id}/take`);
      } catch {
        // handled by mutation error state
      }
    }
  };

  const scoreStyle =
    assessment.score !== null ? getMasteryStyle(assessment.score) : null;

  const actionLabel =
    assessment.attemptStatus === "COMPLETED"
      ? "View results"
      : assessment.attemptStatus === "IN_PROGRESS"
        ? "Continue"
        : "Start";

  return (
    <div className="bg-white rounded-xl border border-brand-border p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-sans text-xs font-bold uppercase tracking-wide text-brand-muted">
              {assessment.assessmentType === "DIAGNOSTIC"
                ? "Diagnostic"
                : "Assessment"}
            </span>
            {assessment.questionCount && (
              <span className="text-xs text-brand-muted">
                · {assessment.questionCount}Q
              </span>
            )}
          </div>
          <h3 className="font-display font-bold text-base text-brand-ink leading-snug">
            {assessment.title}
          </h3>
        </div>
        {scoreStyle && (
          <span
            className={`font-sans font-extrabold text-lg ${scoreStyle.textClass} flex-shrink-0`}
          >
            {Math.round(assessment.score! * 100)}%
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <StatusBadge status={assessment.attemptStatus} />
        <DueChip deadline={assessment.deadline} />
      </div>

      {assessment.status === "ACTIVE" &&
        assessment.attemptStatus !== "COMPLETED" && (
          <button
            onClick={handleAction}
            disabled={startAssessment.isPending}
            className="mt-1 w-full bg-brand-primary text-white font-sans font-semibold text-sm py-2 rounded-full hover:bg-brand-primary/90 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {startAssessment.isPending ? "Starting…" : actionLabel}
          </button>
        )}
      {assessment.attemptStatus === "COMPLETED" && (
        <button
          onClick={handleAction}
          className="mt-1 w-full border border-brand-border text-brand-ink font-sans font-semibold text-sm py-2 rounded-full hover:bg-gray-50 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function AssessmentsTab({ classId }: AssessmentsTabProps) {
  const { data: allAssessments, isPending, isError } = useMyAssessments();

  if (isError) {
    return (
      <div className="text-center py-16 px-6">
        <p className="font-sans text-sm text-brand-body">
          Something went wrong loading assessments. Please refresh the page.
        </p>
      </div>
    );
  }

  if (isPending) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-28 bg-brand-border rounded-xl animate-pulse"
          />
        ))}
      </div>
    );
  }

  const classAssessments = (allAssessments ?? []).filter(
    (a) => a.classId === classId,
  );

  if (classAssessments.length === 0) {
    return (
      <div className="text-center py-16 px-6">
        <ClipboardList
          className="w-10 h-10 text-brand-muted mx-auto mb-4"
          aria-hidden="true"
        />
        <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
          No assessments yet
        </h3>
        <p className="font-sans text-brand-body text-sm max-w-sm mx-auto">
          Your teacher will publish assessments for this class soon.
        </p>
      </div>
    );
  }

  const diagnostics = classAssessments.filter(
    (a) => a.assessmentType === "DIAGNOSTIC",
  );
  const teacherAssessments = classAssessments.filter(
    (a) => a.assessmentType !== "DIAGNOSTIC",
  );

  return (
    <div className="space-y-6">
      {diagnostics.length > 0 && (
        <section>
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3">
            Diagnostic
          </h2>
          <div className="space-y-3">
            {diagnostics.map((a) => (
              <AssessmentCard key={a.id} assessment={a} />
            ))}
          </div>
        </section>
      )}
      {teacherAssessments.length > 0 && (
        <section>
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3">
            Assessments
          </h2>
          <div className="space-y-3">
            {teacherAssessments.map((a) => (
              <AssessmentCard key={a.id} assessment={a} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
