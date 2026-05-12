/**
 * DiagnosticStartPage — handles the "start diagnostic" flow for a class.
 *
 * Route: /student/classes/:classId/diagnostic
 *
 * This page is reached when a student has NOT yet started the diagnostic for a
 * class (no attemptId exists). It fetches the class's diagnostic assessment,
 * starts it via the API, then immediately redirects to the take-assessment page.
 *
 * If the student already has an in-progress attempt (e.g. they navigated back),
 * the start endpoint is idempotent and returns the existing attempt.
 */
import { useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { StudentLayout } from "@kaihle/ui";
import { apiClient } from "@kaihle/auth";
import { useStartAssessment } from "../../hooks/useAttempt";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";

interface AssessmentApiResponse {
  id: string;
  class_id: string;
  is_system_generated: boolean;
  status: string;
}

interface AssessmentsPage {
  data: AssessmentApiResponse[];
}

function useDiagnosticAssessment(classId: string) {
  return useQuery<AssessmentApiResponse | null>({
    queryKey: ["student", "assessments", "class", classId],
    queryFn: async () => {
      const res = await apiClient.get<AssessmentsPage>(
        `/api/v1/classes/${classId}/assessments`,
        { params: { page: 1, page_size: 50 } },
      );
      return res.data.data.find((a) => a.status === "ACTIVE") ?? null;
    },
    enabled: !!classId,
    staleTime: 2 * 60 * 1000,
  });
}

export function DiagnosticStartPage() {
  const { classId = "" } = useParams<{ classId: string }>();
  console.log("classId from useParams:", classId);
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();
  const { data: assessment, isError: isFetchError } =
    useDiagnosticAssessment(classId);

  const startAssessment = useStartAssessment();
  const hasStarted = useRef(false);

  useEffect(() => {
    // assessment is undefined while loading, null if no diagnostic exists for
    // this class, and an object once the query resolves.
    if (!assessment || !classId || hasStarted.current) return;
    hasStarted.current = true;

    startAssessment
      .mutateAsync(assessment.id)
      .then((attempt) => {
        navigate(`/student/assessments/${attempt.id}/take`, { replace: true });
      })
      .catch(() => {
        // startAssessment.isError will render the error state below
        hasStarted.current = false;
      });
    // startAssessment is intentionally omitted — it is a stable mutation object;
    // adding it would cause the effect to fire on every render in concurrent mode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assessment, classId, navigate]);

  const isError = isFetchError || startAssessment.isError;

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
      <div className="flex flex-col items-center justify-center min-h-[40vh] space-y-4">
        {isError ? (
          <>
            <p className="font-sans text-sm text-brand-red text-center">
              Could not start this diagnostic. Please go back and try again.
            </p>
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="bg-brand-primary text-white px-5 py-2 rounded-full font-sans text-sm hover:opacity-90 transition-opacity"
            >
              Go back
            </button>
          </>
        ) : (
          <>
            <div className="w-8 h-8 border-4 border-brand-primary border-t-transparent rounded-full animate-spin" />
            <p className="font-sans text-sm text-brand-body">
              Preparing your diagnostic…
            </p>
          </>
        )}
      </div>
    </StudentLayout>
  );
}
