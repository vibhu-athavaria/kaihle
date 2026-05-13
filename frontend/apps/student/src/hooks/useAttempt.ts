/**
 * Hooks for interacting with assessment attempts.
 * All API calls go through apiClient which auto-attaches the Bearer token.
 *
 * Endpoints exercised:
 *   GET  /api/v1/attempts/:attemptId          → fetch attempt + questions
 *   POST /api/v1/attempts/:attemptId/responses → save single answer
 *   POST /api/v1/attempts/:attemptId/submit    → submit entire attempt
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ─────────────────────────────────────────────────────────────
//  Types
// ─────────────────────────────────────────────────────────────

/** A single MCQ option as returned by the backend. */
export interface QuestionOption {
  key: string; // "A" | "B" | "C" | "D"
  text: string;
}

/** One question inside an attempt. */
export interface AttemptQuestion {
  question_id: string;
  question_text: string;
  question_type: string; // "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER"
  options: QuestionOption[];
  difficulty_level: number; // 0–5; 0 = unset
  subtopic_name: string;
}

/** One saved response — used to hydrate state on resume. */
export interface StudentResponseItem {
  question_id: string;
  selected_key: string;
  is_correct: boolean | null;
}

/** Status values mirroring AssessmentAttemptStatus enum in the backend. */
export type AttemptStatus = "IN_PROGRESS" | "COMPLETED" | "TIMED_OUT";

/**
 * Full attempt payload returned by GET /api/v1/attempts/:attemptId
 * Includes metadata AND the question list.
 */
export interface AttemptResponse {
  id: string;
  assessment_id: string;
  student_id: string;
  title: string;
  status: AttemptStatus;
  started_at: string; // ISO 8601
  submitted_at: string | null;
  score: number | null; // 0.0–1.0 or null while IN_PROGRESS
  questions: AttemptQuestion[]; // full pool for adaptive difficulty
  num_questions: number; // configured count to ask (not pool size)
  responses: StudentResponseItem[]; // previously saved answers for resuming
}

/** One answer entry in the bulk-submit body. */
export interface AttemptAnswer {
  question_id: string;
  selected_key: string;
}

/**
 * Result payload returned by POST /api/v1/attempts/:attemptId/submit
 * Contains the final score and number of correct answers.
 */
export interface AttemptResultResponse {
  attempt_id: string;
  score: number; // 0.0–1.0
  correct_count: number;
  total_questions: number;
  status: AttemptStatus;
  assessment_type: "DIAGNOSTIC" | "PROGRESS_CHECK";
}

// ─────────────────────────────────────────────────────────────
//  Hooks
// ─────────────────────────────────────────────────────────────

/**
 * Fetches a single attempt (including its question list) by ID.
 *
 * - `refetchOnWindowFocus: false` prevents disrupting an in-progress assessment
 *   when the student switches between browser tabs.
 */
export function useAttempt(attemptId: string) {
  return useQuery<AttemptResponse>({
    queryKey: ["student", "attempt", attemptId],
    queryFn: async () => {
      const res = await apiClient.get<AttemptResponse>(
        `/api/v1/attempts/${attemptId}`,
      );
      return res.data;
    },
    enabled: !!attemptId,
    staleTime: 0, // always refetch on remount to get latest responses
    refetchOnWindowFocus: false, // don't disrupt mid-assessment
  });
}

// ─── Start Tier 2 assessment (lazy attempt creation) ─────────

/**
 * POST /api/v1/assessments/:assessmentId/start
 * Idempotent — returns existing attempt or creates one on first call.
 * Used for teacher-created (Tier 2) assessments where no attemptId exists yet.
 */
export function useStartAssessment() {
  return useMutation<AttemptResponse, Error, string>({
    mutationFn: async (assessmentId: string) => {
      const res = await apiClient.post<AttemptResponse>(
        `/api/v1/assessments/${assessmentId}/start`,
      );
      return res.data;
    },
  });
}

// ─── Save single answer ──────────────────────────────────────

interface SubmitResponseVars {
  attemptId: string;
  questionId: string;
  selectedKey: string;
}

/**
 * Saves a single question response in the background.
 * Called automatically after the student selects an option and clicks Next.
 * Failures are surfaced via `isError` — they do NOT block page navigation.
 */
export function useSubmitResponse() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, SubmitResponseVars>({
    mutationFn: async ({ attemptId, questionId, selectedKey }) => {
      await apiClient.post(`/api/v1/attempts/${attemptId}/responses`, {
        question_id: questionId,
        selected_key: selectedKey,
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate attempt query so fresh data is loaded on return
      queryClient.invalidateQueries({
        queryKey: ["student", "attempt", variables.attemptId],
      });
    },
  });
}

// ─── Submit entire attempt ───────────────────────────────────

interface SubmitAttemptVars {
  attemptId: string;
  answers: AttemptAnswer[];
}

/**
 * Submits the entire attempt with all collected answers.
 * Triggers scoring on the backend and returns the result summary.
 */
export function useSubmitAttempt() {
  return useMutation<AttemptResultResponse, Error, SubmitAttemptVars>({
    mutationFn: async ({ attemptId, answers }) => {
      const res = await apiClient.post<AttemptResultResponse>(
        `/api/v1/attempts/${attemptId}/submit`,
        { answers },
      );
      return res.data;
    },
  });
}
