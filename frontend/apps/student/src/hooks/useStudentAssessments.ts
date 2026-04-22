import { useQueries, useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface AssessmentApiResponse {
  id: string;
  class_id: string;
  title: string;
  assessment_type: string;
  is_system_generated: boolean;
  status: string;
  question_count: number;
  deadline: string | null;
  published_at: string | null;
}

interface AssessmentsPage {
  data: AssessmentApiResponse[];
}

interface AttemptHistoryItem {
  attempt_id: string;
  assessment_id: string;
  status: string;
  score: number | null;
}

interface AttemptsPage {
  data: AttemptHistoryItem[];
}

export type AttemptStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";

export interface AssessmentItem {
  id: string;
  classId: string;
  title: string;
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK";
  isSystemGenerated: boolean;
  status: "DRAFT" | "ACTIVE" | "CLOSED";
  questionCount: number;
  deadline: string | null;
  publishedAt: string | null;
  attemptStatus: AttemptStatus;
  attemptId: string | null;
  score: number | null;
}

export interface UseStudentAssessmentsResult {
  diagnostics: AssessmentItem[];
  teacherAssessments: AssessmentItem[];
  newCount: number;
  isPending: boolean;
  isError: boolean;
}

function toAssessmentType(raw: string): AssessmentItem["assessmentType"] {
  if (raw === "DIAGNOSTIC" || raw === "PROGRESS_CHECK") return raw;
  return "PROGRESS_CHECK";
}

function toAssessmentStatus(raw: string): AssessmentItem["status"] {
  if (raw === "DRAFT" || raw === "ACTIVE" || raw === "CLOSED") return raw;
  return "DRAFT";
}

export function useStudentAssessments(
  classIds: string[],
  studentId: string | undefined,
): UseStudentAssessmentsResult {
  const assessmentQueries = useQueries({
    queries: classIds.map((classId) => ({
      queryKey: ["student", "assessments", "class", classId] as const,
      queryFn: async (): Promise<AssessmentApiResponse[]> => {
        const res = await apiClient.get<AssessmentsPage>(
          `/api/v1/classes/${classId}/assessments`,
          { params: { page: 1, page_size: 50 } },
        );
        return res.data.data;
      },
      staleTime: 2 * 60 * 1000,
      // enabled omitted: when classIds is empty, useQueries receives [] and fires no queries
    })),
  });

  const attemptsQuery = useQuery({
    queryKey: ["student", "attempts", studentId] as const,
    queryFn: async (): Promise<AttemptHistoryItem[]> => {
      // No /me shortcut exists for this endpoint — students access their own attempts
      // via their JWT-verified student_id. See attempts.py:272 for the STUDENT role guard.
      const res = await apiClient.get<AttemptsPage>(
        `/api/v1/students/${studentId}/attempts`,
        { params: { page: 1, page_size: 50 } },
      );
      return res.data.data;
    },
    staleTime: 2 * 60 * 1000,
    enabled: !!studentId,
  });

  const isPending =
    (classIds.length > 0 && assessmentQueries.some((q) => q.isPending)) ||
    (!!studentId && attemptsQuery.isPending);
  const isError =
    assessmentQueries.some((q) => q.isError) || attemptsQuery.isError;

  // Build attempt lookup keyed by assessment_id.
  // The attempts endpoint returns newest-first (see attempts.py order_by desc).
  // If a student has retaken an assessment, the first entry encountered wins,
  // which is the most recent attempt — the intended behaviour.
  const attemptMap = new Map<string, AttemptHistoryItem>();
  for (const a of attemptsQuery.data ?? []) {
    attemptMap.set(a.assessment_id, a);
  }

  function toAttemptStatus(
    attempt: AttemptHistoryItem | undefined,
  ): AttemptStatus {
    if (!attempt) return "NOT_STARTED";
    if (attempt.status === "SUBMITTED") return "COMPLETED";
    return "IN_PROGRESS";
  }

  const allAssessments: AssessmentItem[] = assessmentQueries
    .flatMap((q) => q.data ?? [])
    .map((a): AssessmentItem => {
      const attempt = attemptMap.get(a.id);
      return {
        id: a.id,
        classId: a.class_id,
        title: a.title,
        assessmentType: toAssessmentType(a.assessment_type),
        isSystemGenerated: a.is_system_generated,
        status: toAssessmentStatus(a.status),
        questionCount: a.question_count,
        deadline: a.deadline,
        publishedAt: a.published_at,
        attemptStatus: toAttemptStatus(attempt),
        attemptId: attempt?.attempt_id ?? null,
        score: attempt?.score ?? null,
      };
    });

  const diagnostics = allAssessments.filter((a) => a.isSystemGenerated);
  const teacherAssessments = allAssessments.filter((a) => !a.isSystemGenerated);

  const newCount = teacherAssessments.filter(
    (a) => a.status === "ACTIVE" && a.attemptStatus === "NOT_STARTED",
  ).length;

  return { diagnostics, teacherAssessments, newCount, isPending, isError };
}
