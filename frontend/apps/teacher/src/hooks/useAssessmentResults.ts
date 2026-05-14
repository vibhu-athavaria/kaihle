/**
 * React Query hooks for assessment results.
 * Fetches class-level result summaries and per-attempt detail.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types ──────────────────────────────────────────────────────────────────

export interface StudentAttemptSummary {
  attempt_id: string | null;
  student_id: string;
  student_name: string;
  /** Float 0.0–1.0, or null if not submitted */
  score: number | null;
  submitted_at: string | null;
  status: "COMPLETED" | "IN_PROGRESS" | "NOT_STARTED";
}

export interface TopicBreakdownItem {
  topic_name: string;
  correct_count: number;
  total_count: number;
  /** Fraction 0.0–1.0 */
  avg_score: number;
}

export interface AssessmentResultsSummary {
  assessment_id: string;
  assessment_title: string;
  assessment_type: "DIAGNOSTIC" | "TOPIC_SPECIFIC" | "PROGRESS_CHECK" | "FINAL";
  class_id: string;
  class_name: string;
  total_students: number;
  submitted_count: number;
  attempts: StudentAttemptSummary[];
  topic_breakdown: TopicBreakdownItem[];
}

export interface QuestionAttempt {
  question_id: string;
  question_text: string;
  subtopic_name: string;
  topic_name: string;
  difficulty_level: number; // 1–5
  /** The key (A/B/C/D) the student chose, or null if skipped */
  selected_key: string | null;
  /** The key that is correct */
  correct_answer: string;
  is_correct: boolean;
  position: number;
}

export interface AttemptDetailResult {
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  assessment_type: "DIAGNOSTIC" | "TOPIC_SPECIFIC" | "PROGRESS_CHECK" | "FINAL";
  student_id: string;
  student_name: string;
  score: number | null;
  submitted_at: string | null;
  status: "COMPLETED" | "IN_PROGRESS" | "NOT_STARTED";
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
    queryKey: ["attempt-detail", attemptId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/attempts/${attemptId}/detail`);
      return res.data;
    },
    staleTime: 60_000,
    enabled: !!attemptId,
  });
}
