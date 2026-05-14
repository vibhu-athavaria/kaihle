/**
 * AssessmentResultsPage — shown after a student submits an attempt.
 *
 * Route: /student/assessments/:attemptId/results
 *
 * Data sources:
 *   1. Router location.state.result (passed from TakeAssessmentPage submit) — score summary
 *   2. GET /api/v1/attempts/:attemptId/results — fallback score summary
 *   3. GET /api/v1/attempts/:attemptId/review  — full per-question breakdown (always fetched)
 *
 * Design: DESIGN_SYSTEM.md §5.4 — green actions, Fraunces headings, Nunito body.
 */
import { useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle, XCircle, Minus } from "lucide-react";
import { apiClient } from "@kaihle/auth";
import { StudentLayout, ScoreRing, Skeleton } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import {
  useAttemptReview,
  type AttemptResultResponse,
  type AttemptReviewItem,
} from "../../hooks/useAttempt";

// ─────────────────────────────────────────────────────────────
//  Results skeleton
// ─────────────────────────────────────────────────────────────

function ResultsSkeleton() {
  return (
    <div className="flex flex-col items-center space-y-6 py-12">
      <Skeleton className="w-[140px] h-[140px] rounded-full" />
      <Skeleton className="h-6 w-40 rounded-full" />
      <Skeleton className="h-4 w-32 rounded-full" />
      <Skeleton className="h-10 w-48 rounded-full" />
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div className="w-full bg-white rounded-xl border border-role-student-border overflow-hidden">
      {/* thead skeleton */}
      <div className="flex gap-4 px-4 py-2.5 border-b border-role-student-border bg-gray-50">
        <Skeleton className="h-3 w-1/2 rounded-full" />
        <Skeleton className="h-3 w-1/4 rounded-full" />
        <Skeleton className="h-3 w-1/4 rounded-full" />
      </div>
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="flex gap-4 px-4 py-3.5 border-b last:border-b-0 border-role-student-border"
        >
          <Skeleton className="h-4 w-1/2 rounded-full" />
          <Skeleton className="h-4 w-1/4 rounded-full" />
          <Skeleton className="h-4 w-1/4 rounded-full" />
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────

function lookupOptionText(
  options: AttemptReviewItem["options"],
  key: string | null,
): string | null {
  if (key === null || key === "") return null;
  return options.find((o) => o.key === key)?.text ?? key;
}

// ─────────────────────────────────────────────────────────────
//  Compact per-question review row (used inside QuestionReviewTable)
// ─────────────────────────────────────────────────────────────

function QuestionReviewRow({ item }: { item: AttemptReviewItem }) {
  const isUnanswered = item.selected_key === null || item.selected_key === "";
  const correctText = lookupOptionText(item.options, item.correct_answer);
  const selectedText = isUnanswered
    ? null
    : lookupOptionText(item.options, item.selected_key);

  // Row-level outcome: correct / wrong / unanswered
  const rowBg = item.is_correct
    ? "bg-brand-green-light border-l-[3px] border-l-brand-green"
    : "bg-red-50 border-l-[3px] border-l-red-400";

  return (
    <li
      className={[
        "flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4",
        "px-4 py-3.5 border-b last:border-b-0 border-role-student-border",
        rowBg,
      ].join(" ")}
      // Announce outcome to screen readers without relying on color
      aria-label={
        item.is_correct
          ? `Question ${item.position}: Correct`
          : isUnanswered
            ? `Question ${item.position}: Not answered`
            : `Question ${item.position}: Incorrect`
      }
    >
      {/* ── Column 1: Question ──────────────────────────────── */}
      <div className="flex items-start gap-2.5 sm:flex-[3] min-w-0">
        {/* Outcome icon — non-color signal */}
        <span className="flex-shrink-0 mt-0.5" aria-hidden="true">
          {item.is_correct ? (
            <CheckCircle className="w-4 h-4 text-brand-green" />
          ) : isUnanswered ? (
            <Minus className="w-4 h-4 text-brand-muted" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
        </span>
        <div className="min-w-0">
          <span className="block font-sans text-[11px] font-bold text-brand-muted mb-0.5 uppercase tracking-wide">
            Q{item.position} · {item.subtopic_name}
          </span>
          {/* Wrap gracefully; truncate only on very small viewports */}
          <p className="font-sans text-sm text-brand-ink leading-snug line-clamp-3 sm:line-clamp-none">
            {item.question_text}
          </p>
        </div>
      </div>

      {/* ── Column 2: Correct answer ─────────────────────────── */}
      <div className="sm:flex-1 sm:min-w-0 pl-[26px] sm:pl-0">
        <span className="block font-sans text-[10px] font-bold text-brand-muted uppercase tracking-wide mb-0.5 sm:hidden">
          Correct answer
        </span>
        <span className="font-sans text-sm text-brand-green font-medium leading-snug">
          {correctText ?? item.correct_answer}
        </span>
      </div>

      {/* ── Column 3: Your answer ─────────────────────────────── */}
      <div className="sm:flex-1 sm:min-w-0 pl-[26px] sm:pl-0">
        <span className="block font-sans text-[10px] font-bold text-brand-muted uppercase tracking-wide mb-0.5 sm:hidden">
          Your answer
        </span>
        {isUnanswered ? (
          <span className="font-sans text-sm text-brand-muted italic">
            Not answered
          </span>
        ) : item.is_correct ? (
          <span className="font-sans text-sm text-brand-green font-medium leading-snug">
            {selectedText ?? item.selected_key}
          </span>
        ) : (
          <span className="font-sans text-sm text-red-600 font-medium leading-snug line-through decoration-red-400">
            {selectedText ?? item.selected_key}
          </span>
        )}
      </div>
    </li>
  );
}

// ─────────────────────────────────────────────────────────────
//  Question review table (heading + list)
// ─────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

function QuestionReviewTable({
  questions,
}: {
  questions: AttemptReviewItem[];
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.ceil(questions.length / PAGE_SIZE);
  const pageItems = questions.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <section aria-label="Question-by-question review" className="w-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-bold text-lg text-brand-ink">
          Review your answers
        </h2>
        <span className="font-sans text-xs text-brand-muted">
          {questions.length} questions
        </span>
      </div>

      {/* Column header — visible on sm+ only */}
      <div
        className="hidden sm:flex gap-4 px-4 py-2 bg-gray-50 border border-role-student-border rounded-t-xl border-b-0"
        aria-hidden="true"
      >
        <span className="flex-[3] font-sans text-xs font-bold uppercase tracking-wide text-brand-muted">
          Question
        </span>
        <span className="flex-1 font-sans text-xs font-bold uppercase tracking-wide text-brand-muted">
          Correct answer
        </span>
        <span className="flex-1 font-sans text-xs font-bold uppercase tracking-wide text-brand-muted">
          Your answer
        </span>
      </div>

      <ul
        className={[
          "bg-white border border-role-student-border overflow-hidden",
          "rounded-xl sm:rounded-t-none sm:rounded-b-xl",
        ].join(" ")}
      >
        {pageItems.map((item) => (
          <QuestionReviewRow key={item.question_id} item={item} />
        ))}
      </ul>

      {/* Pagination controls — only shown when more than one page */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-3">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(p - 1, 1))}
            disabled={page === 1}
            className="font-sans text-sm text-brand-primary disabled:text-brand-muted disabled:cursor-not-allowed hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          >
            ← Previous
          </button>
          <span className="font-sans text-xs text-brand-muted">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            disabled={page === totalPages}
            className="font-sans text-sm text-brand-primary disabled:text-brand-muted disabled:cursor-not-allowed hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          >
            Next →
          </button>
        </div>
      )}
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
//  Main component
// ─────────────────────────────────────────────────────────────

export function AssessmentResultsPage() {
  const { attemptId = "" } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const layout = useStudentLayoutProps();

  // ── Score summary ───────────────────────────────────────────
  const routerResult =
    (location.state as { result?: AttemptResultResponse } | null)?.result ??
    null;

  const {
    data: fetchedResult,
    isLoading: isResultLoading,
    isError: isResultError,
  } = useQuery<AttemptResultResponse>({
    queryKey: ["student", "attempt-result", attemptId],
    queryFn: async () => {
      const res = await apiClient.get<AttemptResultResponse>(
        `/api/v1/attempts/${attemptId}/results`,
      );
      return res.data;
    },
    enabled: !routerResult && !!attemptId,
  });

  const result = routerResult ?? fetchedResult;

  // ── Per-question review ─────────────────────────────────────
  const { data: review, isLoading: isReviewLoading } =
    useAttemptReview(attemptId);

  // ── Mastery style for score ring label ─────────────────────
  const masteryStyle = getMasteryStyle(result?.score ?? null);

  const isLoading = (isResultLoading && !routerResult) || isReviewLoading;

  // ─────────────────────────────────────────────────────────────
  //  Render
  // ─────────────────────────────────────────────────────────────

  return (
    <StudentLayout
      activeNav="assessments"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      assessmentBadge={layout.assessmentBadge}
      onLogout={layout.onLogout}
    >
      {isResultLoading && !routerResult ? (
        <ResultsSkeleton />
      ) : isResultError && !routerResult ? (
        <div className="text-center py-12">
          <p className="text-brand-red font-sans text-sm mb-4">
            Could not load your results. Please try again.
          </p>
          <button
            type="button"
            onClick={() => navigate("/student/dashboard")}
            className="bg-brand-primary text-white px-5 py-2.5 rounded-full font-sans text-sm hover:bg-brand-dark transition-colors"
          >
            Back to Dashboard
          </button>
        </div>
      ) : result ? (
        <div className="max-w-2xl mx-auto flex flex-col items-center gap-6 py-8">
          {/* ── Score ring ────────────────────────────────────── */}
          <div className="flex flex-col items-center gap-3">
            <ScoreRing score={result.score} size="lg" />
            <p
              className={[
                "font-sans font-bold text-sm",
                masteryStyle.textClass,
              ].join(" ")}
            >
              {masteryStyle.label}
            </p>
          </div>

          {/* ── Correct count ─────────────────────────────────── */}
          <p className="font-sans text-sm text-brand-body text-center">
            <span className="font-semibold text-brand-ink">
              {result.correct_count}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-brand-ink">
              {result.total_questions}
            </span>{" "}
            correct
          </p>

          {/* ── Per-question review ────────────────────────────── */}
          <div className="w-full pt-2">
            {isLoading || isReviewLoading ? (
              <>
                <h2 className="font-display font-bold text-lg text-brand-ink mb-3">
                  Review your answers
                </h2>
                <ReviewSkeleton />
              </>
            ) : review?.questions && review.questions.length > 0 ? (
              <QuestionReviewTable questions={review.questions} />
            ) : (
              <>
                <h2 className="font-display font-bold text-lg text-brand-ink mb-3">
                  Review your answers
                </h2>
                <p className="font-sans text-sm text-brand-muted">
                  No question breakdown available.
                </p>
              </>
            )}
          </div>

          {/* ── CTA ───────────────────────────────────────────── */}
          <button
            type="button"
            onClick={() =>
              navigate(
                !result.assessment_type ||
                  result.assessment_type === "DIAGNOSTIC"
                  ? "/student/dashboard"
                  : "/student/my-progress",
              )
            }
            className="w-full bg-brand-primary text-white px-6 py-3 rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            {!result.assessment_type || result.assessment_type === "DIAGNOSTIC"
              ? "Back to Dashboard"
              : "View my progress →"}
          </button>
        </div>
      ) : null}
    </StudentLayout>
  );
}
