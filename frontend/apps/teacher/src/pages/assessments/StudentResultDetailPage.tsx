/**
 * StudentResultDetailPage — per-student question breakdown for an assessment attempt.
 *
 * Route: /teacher/assessments/:assessmentId/results/:studentId
 * Query param: ?attempt={attemptId}
 *
 * Sections:
 *   1. Page header — student name, score ring, assessment type badge
 *   2. QuestionBreakdown — correct/wrong answers with pagination
 */
import { useParams, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { DashboardLayout } from "@kaihle/ui";
import { useAttemptResult } from "../../hooks/useAssessmentResults";
import type {
  QuestionAttempt,
  TopicBreakdownItem,
} from "../../hooks/useAssessmentResults";
import { ScoreRing } from "../../components/results/ScoreRing";
import { QuestionBreakdown } from "../../components/results/QuestionBreakdown";
import { TopicPerformanceBreakdown } from "../../components/results/TopicPerformanceBreakdown";
import { ChevronLeft } from "lucide-react";

function buildTopicBreakdown(
  questions: QuestionAttempt[],
): TopicBreakdownItem[] {
  const map = new Map<string, { correct: number; total: number }>();
  for (const q of questions) {
    const entry = map.get(q.topic_name) ?? { correct: 0, total: 0 };
    entry.total += 1;
    if (q.is_correct) entry.correct += 1;
    map.set(q.topic_name, entry);
  }
  return Array.from(map.entries())
    .map(([topic_name, { correct, total }]) => ({
      topic_name,
      correct_count: correct,
      total_count: total,
      avg_score: total > 0 ? correct / total : 0,
    }))
    .sort((a, b) => a.avg_score - b.avg_score);
}

// ── Assessment type badge config ──────────────────────────────────────────

const TYPE_BADGE: Record<string, { label: string; className: string }> = {
  DIAGNOSTIC: {
    label: "Diagnostic",
    className: "bg-blue-50 text-blue-700 border-blue-200",
  },
  TOPIC_SPECIFIC: {
    label: "Topic Specific",
    className: "bg-purple-50 text-purple-700 border-purple-200",
  },
  PROGRESS_CHECK: {
    label: "Progress Check",
    className: "bg-orange-50 text-orange-700 border-orange-200",
  },
  FINAL: {
    label: "Final",
    className: "bg-gray-100 text-gray-600 border-gray-200",
  },
};

// ── Component ─────────────────────────────────────────────────────────────

function StudentDetailContent({
  assessmentId,
  attemptId,
}: {
  assessmentId: string;
  attemptId: string | null;
}) {
  const { data, isLoading, isError } = useAttemptResult(attemptId ?? undefined);

  if (isError) {
    return (
      <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm">
        Failed to load student result details. Please try again.
      </div>
    );
  }

  const typeBadge = data
    ? (TYPE_BADGE[data.assessment_type] ?? TYPE_BADGE["FINAL"])
    : null;

  return (
    <div className="p-6 space-y-6">
      {/* Back nav */}
      <Link
        to={`/teacher/assessments/${assessmentId}/results`}
        className="inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded"
      >
        <ChevronLeft className="w-4 h-4" aria-hidden="true" />
        Back to class results
      </Link>

      {/* Header card — student name + score ring */}
      <div className="bg-white rounded-2xl border border-brand-border p-6">
        {isLoading ? (
          <div className="animate-pulse flex items-center gap-6">
            <div className="w-24 h-24 bg-gray-100 rounded-full" />
            <div className="space-y-2">
              <div className="h-6 w-48 bg-gray-200 rounded" />
              <div className="h-4 w-32 bg-gray-100 rounded" />
            </div>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
            {/* Score ring */}
            <ScoreRing score={data?.score ?? null} />

            {/* Student info */}
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="font-display font-bold text-2xl text-brand-ink">
                  {data?.student_name ?? "Student"}
                </h1>
                {typeBadge && (
                  <span
                    className={`border rounded-full px-3 py-0.5 text-xs font-bold ${typeBadge.className}`}
                  >
                    {typeBadge.label}
                  </span>
                )}
              </div>
              <p className="text-sm text-brand-muted">
                {data?.assessment_title ?? "Assessment"}
              </p>
              {data?.submitted_at && (
                <p className="text-xs text-brand-muted mt-1">
                  Submitted{" "}
                  {new Date(data.submitted_at).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Per-topic summary */}
      {(isLoading || (data?.questions?.length ?? 0) > 0) && (
        <div className="bg-white rounded-2xl border border-brand-border p-5">
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
            Topic summary
          </h2>
          <TopicPerformanceBreakdown
            topics={buildTopicBreakdown(data?.questions ?? [])}
            isLoading={isLoading}
          />
        </div>
      )}

      {/* Question breakdown */}
      <div>
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          Question breakdown
        </h2>
        {isLoading ? (
          <div className="animate-pulse space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-24 bg-gray-100 rounded-xl" />
            ))}
          </div>
        ) : (
          <QuestionBreakdown questions={data?.questions ?? []} />
        )}
      </div>
    </div>
  );
}

export function StudentResultDetailPage() {
  const { assessmentId } = useParams<{
    assessmentId: string;
    studentId: string;
  }>();
  const [searchParams] = useSearchParams();
  const attemptId = searchParams.get("attempt");
  const { logout } = useAuth();

  if (!assessmentId) {
    return (
      <DashboardLayout
        variant="teacher"
        pageTitle="Student Result"
        onLogout={logout}
      >
        <div className="p-6 text-red-600">Invalid assessment ID.</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      variant="teacher"
      pageTitle="Student Result"
      onLogout={logout}
    >
      <StudentDetailContent assessmentId={assessmentId} attemptId={attemptId} />
    </DashboardLayout>
  );
}
