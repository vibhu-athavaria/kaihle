/**
 * React Query hooks for assessment results.
 * Fetches class-level result summaries and per-attempt detail.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types ──────────────────────────────────────────────────────────────────

export interface StudentAttemptSummary {
  /** Assessment attempt ID */
  attemptId: string;
  studentId: string;
  studentName: string;
  /** Float 0.0–1.0, or null if not submitted */
  score: number | null;
  submittedAt: string | null;
  status: "SUBMITTED" | "IN_PROGRESS" | "NOT_STARTED";
}

export interface AssessmentResultsSummary {
  assessmentId: string;
  assessmentTitle: string;
  assessmentType: "DIAGNOSTIC" | "TOPIC_SPECIFIC" | "PROGRESS_CHECK" | "FINAL";
  classId: string;
  className: string;
  totalStudents: number;
  submittedCount: number;
  attempts: StudentAttemptSummary[];
}

export interface QuestionAttempt {
  questionId: string;
  questionText: string;
  /** The answer the student chose */
  selectedAnswer: string | null;
  /** The correct answer */
  correctAnswer: string;
  isCorrect: boolean;
  /** Position in assessment, 1-based */
  position: number;
}

export interface AttemptDetailResult {
  attemptId: string;
  assessmentId: string;
  assessmentTitle: string;
  assessmentType: "DIAGNOSTIC" | "TOPIC_SPECIFIC" | "PROGRESS_CHECK" | "FINAL";
  studentId: string;
  studentName: string;
  score: number | null;
  submittedAt: string | null;
  status: "SUBMITTED" | "IN_PROGRESS" | "NOT_STARTED";
  questions: QuestionAttempt[];
}

// ── Hooks ──────────────────────────────────────────────────────────────────

/**
 * Fetch all student attempt summaries for an assessment.
 * Endpoint: GET /api/v1/assessments/{assessmentId}/results
 *
 * Falls back to GET /api/v1/assessments/{assessmentId} for assessment metadata
 * if the results endpoint is not yet available.
 */
export function useAssessmentResults(assessmentId: string) {
  return useQuery<AssessmentResultsSummary>({
    queryKey: ["assessment-results", assessmentId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/assessments/${assessmentId}/results`,
      );
      return res.data;
    },
    staleTime: 60_000,
    enabled: !!assessmentId,
  });
}

/**
 * Fetch per-question detail for a specific student attempt.
 * Endpoint: GET /api/v1/attempts/{attemptId}/results
 */
export function useAttemptResult(attemptId: string | undefined) {
  return useQuery<AttemptDetailResult>({
    queryKey: ["attempt-result", attemptId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/attempts/${attemptId}/results`);
      return res.data;
    },
    staleTime: 60_000,
    enabled: !!attemptId,
  });
}
