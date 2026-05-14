/**
 * AssessmentResultsPage — class overview of all student results for an assessment.
 *
 * Route: /teacher/assessments/:assessmentId/results
 *
 * Sections:
 *   1. Page header — assessment title + type badge
 *   2. ResultsKPIRow — 4 summary cards
 *   3. ScoreDistributionChart — horizontal bars by mastery band
 *   4. StudentResultsTable — sortable, searchable table with "View answers" links
 *
 * Assessment type badges:
 *   DIAGNOSTIC | TOPIC_SPECIFIC | PROGRESS_CHECK | FINAL
 *   Each has a distinct colour per spec.
 */
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { DashboardLayout } from "@kaihle/ui";
import { useAssessmentResults } from "../../hooks/useAssessmentResults";
import { ResultsKPIRow } from "../../components/results/ResultsKPIRow";
import { ScoreDistributionChart } from "../../components/results/ScoreDistributionChart";
import { StudentResultsTable } from "../../components/results/StudentResultsTable";
import { TopicPerformanceBreakdown } from "../../components/results/TopicPerformanceBreakdown";
import { ChevronLeft, Map } from "lucide-react";

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

function AssessmentResultsContent({ assessmentId }: { assessmentId: string }) {
  const { data, isLoading, isError } = useAssessmentResults(assessmentId);

  if (isError) {
    return (
      <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm">
        Failed to load assessment results. Please try again.
      </div>
    );
  }

  const typeBadge = data
    ? (TYPE_BADGE[data.assessment_type] ?? TYPE_BADGE["FINAL"])
    : null;

  const attempts = data?.attempts ?? [];

  const backHref = data?.class_id
    ? `/teacher/classes/${data.class_id}/assessments`
    : "/teacher/assessments";

  return (
    <div className="p-6 space-y-6">
      {/* Back nav */}
      <Link
        to={backHref}
        className="inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded"
      >
        <ChevronLeft className="w-4 h-4" aria-hidden="true" />
        Back to assessments
      </Link>

      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          {isLoading ? (
            <div className="animate-pulse">
              <div className="h-7 w-64 bg-gray-200 rounded mb-2" />
              <div className="h-4 w-32 bg-gray-100 rounded" />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="font-display font-bold text-2xl text-brand-ink">
                  {data?.assessment_title ?? "Assessment Results"}
                </h1>
                {typeBadge && (
                  <span
                    className={`border rounded-full px-3 py-0.5 text-xs font-bold ${typeBadge.className}`}
                  >
                    {typeBadge.label}
                  </span>
                )}
              </div>
              {data?.class_name && (
                <p className="text-sm text-brand-muted">{data.class_name}</p>
              )}
            </>
          )}
        </div>
      </div>

      {/* Gap Map callout — only for diagnostic assessments */}
      {data?.assessment_type === "DIAGNOSTIC" &&
        data.class_id &&
        (() => {
          const { submitted_count, total_students, class_id } = data;
          const allSubmitted =
            submitted_count > 0 && submitted_count >= total_students;
          const someSubmitted =
            submitted_count > 0 && submitted_count < total_students;
          const noneSubmitted = submitted_count === 0;

          if (noneSubmitted) {
            return (
              <div className="flex items-center gap-4 bg-gray-50 border border-brand-border rounded-2xl px-5 py-4">
                <Map
                  className="w-5 h-5 text-brand-muted shrink-0"
                  aria-hidden="true"
                />
                <p className="text-sm text-brand-muted">
                  Diagnostic is live — waiting for students to submit their
                  responses. Results will appear here as they come in.
                </p>
              </div>
            );
          }

          if (someSubmitted) {
            return (
              <div className="flex items-center gap-4 bg-blue-50 border border-blue-200 rounded-2xl px-5 py-4">
                <Map
                  className="w-5 h-5 text-blue-600 shrink-0"
                  aria-hidden="true"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-blue-800">
                    {submitted_count} of {total_students} students have
                    submitted
                  </p>
                  <p className="text-xs text-blue-600 mt-0.5">
                    Gap Map is updating as results come in.
                  </p>
                </div>
                <Link
                  to={`/teacher/classes/${class_id}/gap-map`}
                  className="shrink-0 text-sm font-bold text-blue-700 hover:text-blue-900 transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 rounded"
                >
                  View Gap Map →
                </Link>
              </div>
            );
          }

          if (allSubmitted) {
            return (
              <div className="flex items-center gap-4 bg-blue-50 border border-blue-200 rounded-2xl px-5 py-4">
                <Map
                  className="w-5 h-5 text-blue-600 shrink-0"
                  aria-hidden="true"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-blue-800">
                    All students have submitted — diagnostic results are
                    complete
                  </p>
                  <p className="text-xs text-blue-600 mt-0.5">
                    View the Gap Map to see personalised placement for each
                    student.
                  </p>
                </div>
                <Link
                  to={`/teacher/classes/${class_id}/gap-map`}
                  className="shrink-0 text-sm font-bold text-blue-700 hover:text-blue-900 transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 rounded"
                >
                  View Gap Map →
                </Link>
              </div>
            );
          }

          return null;
        })()}

      {/* KPI summary row */}
      <ResultsKPIRow
        isLoading={isLoading}
        totalStudents={data?.total_students ?? 0}
        attempts={attempts}
      />

      {/* Score distribution chart */}
      <div className="bg-white rounded-2xl border border-brand-border p-5">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          Score distribution
        </h2>
        <ScoreDistributionChart attempts={attempts} isLoading={isLoading} />
      </div>

      {/* Topic performance breakdown */}
      {(isLoading || (data?.topic_breakdown?.length ?? 0) > 0) && (
        <div className="bg-white rounded-2xl border border-brand-border p-5">
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
            Topic performance
          </h2>
          <TopicPerformanceBreakdown
            topics={data?.topic_breakdown ?? []}
            isLoading={isLoading}
          />
        </div>
      )}

      {/* Student results table */}
      <div>
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          Student results
        </h2>
        <StudentResultsTable
          assessmentId={assessmentId}
          attempts={attempts}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}

export function AssessmentResultsPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const { logout } = useAuth();

  if (!assessmentId) {
    return (
      <DashboardLayout
        variant="teacher"
        pageTitle="Assessment Results"
        onLogout={logout}
      >
        <div className="p-6 text-red-600">Invalid assessment ID.</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      variant="teacher"
      pageTitle="Assessment Results"
      onLogout={logout}
    >
      <AssessmentResultsContent assessmentId={assessmentId} />
    </DashboardLayout>
  );
}
