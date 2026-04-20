/**
 * AssessmentResultsPage — shown after a student submits an attempt.
 *
 * Route: /student/assessments/:attemptId/results
 *
 * Data source:
 *   1. Router location.state.result (passed from TakeAssessmentPage submit)
 *   2. Fallback: GET /api/v1/attempts/:attemptId/results (direct URL access)
 *
 * Design: DESIGN_SYSTEM.md §5.4 — green actions, Fraunces headings, Nunito body.
 */
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";
import { StudentLayout, ScoreRing, Skeleton } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";
import type { AttemptResultResponse } from "../../hooks/useAttempt";

// ─────────────────────────────────────────────────────────────
//  Result banners
// ─────────────────────────────────────────────────────────────

function DiagnosticBanner() {
  return (
    <div
      className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center"
      role="status"
      aria-live="polite"
    >
      <p className="font-sans font-semibold text-sm text-brand-green">
        Diagnostic complete!{" "}
        <span className="font-normal">
          Head back to see what&apos;s now unlocked.
        </span>
      </p>
    </div>
  );
}

function FormativeBanner() {
  return (
    <div
      className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center"
      role="status"
      aria-live="polite"
    >
      <p className="font-sans font-semibold text-sm text-brand-green">
        Assessment submitted.{" "}
        <span className="font-normal">Your progress has been updated.</span>
      </p>
    </div>
  );
}

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

// ─────────────────────────────────────────────────────────────
//  Main component
// ─────────────────────────────────────────────────────────────

export function AssessmentResultsPage() {
  const { attemptId = "" } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();

  // ── Student layout data ─────────────────────────────────────
  const { data: studentInfo } = useStudentInfo();
  const { data: classesData } = useMyClasses();

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  // ── Result data ─────────────────────────────────────────────
  // Prefer router state (freshly submitted); fall back to API fetch
  const routerResult =
    (location.state as { result?: AttemptResultResponse } | null)?.result ??
    null;

  const {
    data: fetchedResult,
    isLoading,
    isError,
  } = useQuery<AttemptResultResponse>({
    queryKey: ["student", "attempt-result", attemptId],
    queryFn: async () => {
      const res = await apiClient.get<AttemptResultResponse>(
        `/api/v1/attempts/${attemptId}/results`,
      );
      return res.data;
    },
    // Only fetch from API if we don't already have router-state result
    enabled: !routerResult && !!attemptId,
  });

  const result = routerResult ?? fetchedResult;

  // ── Mastery style for score ring label ─────────────────────
  const masteryStyle = getMasteryStyle(result?.score ?? null);

  // ─────────────────────────────────────────────────────────────
  //  Render
  // ─────────────────────────────────────────────────────────────

  return (
    <StudentLayout
      activeNav="assessments"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      {isLoading && !routerResult ? (
        <ResultsSkeleton />
      ) : isError && !routerResult ? (
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
        <div className="max-w-md mx-auto flex flex-col items-center gap-6 py-8">
          {/* ── Result banner — branches on assessment type ── */}
          {!result.assessment_type || result.assessment_type === "DIAGNOSTIC" ? (
            <DiagnosticBanner />
          ) : (
            <FormativeBanner />
          )}

          {/* ── Score ring ─────────────────────────────────── */}
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

          {/* ── Correct count ──────────────────────────────── */}
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

          {/* ── CTA ──────────────────────────────────────────── */}
          <button
            type="button"
            onClick={() =>
              navigate(
                !result.assessment_type || result.assessment_type === "DIAGNOSTIC"
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
