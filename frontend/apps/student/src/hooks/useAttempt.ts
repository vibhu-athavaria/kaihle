/**
 * Hooks for interacting with assessment attempts.
 * All API calls go through apiClient which auto-attaches the Bearer token.
 *
 * Endpoints exercised:
 *   GET  /api/v1/attempts/:attemptId               → fetch attempt metadata
 *   GET  /api/v1/attempts/:attemptId/next-question → adaptively selected question
 *   POST /api/v1/attempts/:attemptId/responses     → save single answer
 *   POST /api/v1/attempts/:attemptId/submit        → submit entire attempt
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
  time_limit_minutes: number; // 0 = untimed
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
  const queryClient = useQueryClient();
  return useMutation<AttemptResponse, Error, string>({
    mutationFn: async (assessmentId: string) => {
      const res = await apiClient.post<AttemptResponse>(
        `/api/v1/assessments/${assessmentId}/start`,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["student", "assessments"] });
    },
  });
}

// ─── Adaptive next question ──────────────────────────────────

/**
 * Payload from GET /api/v1/attempts/:attemptId/next-question
 * The backend picks the question by replaying the student's answers through a
 * per-topic difficulty staircase, so the client never sees the unserved pool.
 */
export interface NextQuestionResponse {
  question: AttemptQuestion | null; // null once the attempt is complete
  answered_count: number;
  question_count: number;
  complete: boolean;
}

/**
 * Fetches the next adaptively-selected question.
 *
 * The endpoint is idempotent — without an intervening answer it returns the same
 * question — so a refetch after a dropped request never skips or burns a question.
 * `staleTime: 0` keeps every refetch authoritative; `gcTime: 0` prevents a stale
 * cached question flashing when the student returns to a resumed attempt.
 */
export function useNextQuestion(attemptId: string, enabled = true) {
  return useQuery<NextQuestionResponse>({
    queryKey: ["student", "attempt", attemptId, "next-question"],
    queryFn: async () => {
      const res = await apiClient.get<NextQuestionResponse>(
        `/api/v1/attempts/${attemptId}/next-question`,
      );
      return res.data;
    },
    enabled: !!attemptId && enabled,
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false, // don't disrupt mid-assessment
  });
}

// ─── Save single answer ──────────────────────────────────────

interface SubmitResponseVars {
  attemptId: string;
  questionId: string;
  selectedKey: string;
  timeTakenMs?: number; // milliseconds spent on this question
}

/** Scoring outcome returned by POST /responses. */
export interface SubmitResponseResult {
  scored: boolean;
  is_correct: boolean;
  next_question_available: boolean;
}

/**
 * Saves a single question response and returns its scoring outcome.
 * The adaptive flow depends on this result to decide whether to advance or finish.
 */
export function useSubmitResponse() {
  const queryClient = useQueryClient();
  return useMutation<SubmitResponseResult, Error, SubmitResponseVars>({
    mutationFn: async ({ attemptId, questionId, selectedKey, timeTakenMs }) => {
      const res = await apiClient.post<SubmitResponseResult>(
        `/api/v1/attempts/${attemptId}/responses`,
        {
          question_id: questionId,
          selected_key: selectedKey,
          time_taken_ms: timeTakenMs ?? null,
        },
      );
      return res.data;
    },
    onSuccess: (_, variables) => {
      // Both the attempt record and the adaptive cursor move on every answer.
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
  timed_out?: boolean;
}

// ─── Per-question review after submission ────────────────────

export interface ReviewOption {
  key: string;
  text: string;
}

export interface AttemptReviewItem {
  position: number;
  question_id: string;
  question_text: string;
  subtopic_name: string;
  topic_name: string;
  difficulty_level: number;
  options: ReviewOption[];
  selected_key: string | null; // null = student never answered (timed out)
  correct_answer: string;
  is_correct: boolean;
}

export interface AttemptReviewResponse {
  attempt_id: string;
  assessment_id: string;
  title: string;
  score: number;
  correct_count: number;
  total_questions: number;
  time_limit_minutes: number;
  timed_out: boolean;
  questions: AttemptReviewItem[];
}

/**
 * Submits the entire attempt with all collected answers.
 * Triggers scoring on the backend and returns the result summary.
 * Invalidates the attempts list and classes list so the assessment page
 * immediately reflects the COMPLETED status without a manual refresh.
 */
export function useSubmitAttempt() {
  const queryClient = useQueryClient();
  return useMutation<AttemptResultResponse, Error, SubmitAttemptVars>({
    mutationFn: async ({ attemptId, answers, timed_out = false }) => {
      const res = await apiClient.post<AttemptResultResponse>(
        `/api/v1/attempts/${attemptId}/submit`,
        { answers, timed_out },
      );
      return res.data;
    },
    onSuccess: () => {
      // Bust dashboard so action_items and diagnostic_status reflect completion.
      queryClient.invalidateQueries({ queryKey: ["student", "dashboard"] });
      // Bust unified assessments query so attemptStatus reflects COMPLETED immediately.
      queryClient.invalidateQueries({ queryKey: ["student", "assessments"] });
      // Bust classes so onboarding_diagnostic_status updates after a diagnostic submit.
      queryClient.invalidateQueries({ queryKey: ["student", "classes"] });
    },
  });
}

/**
 * Fetches the per-question review for a completed attempt.
 * Only accessible by the owning student after submission.
 */
export function useAttemptReview(attemptId: string) {
  return useQuery<AttemptReviewResponse>({
    queryKey: ["student", "attempt", attemptId, "review"],
    queryFn: async () => {
      const res = await apiClient.get<AttemptReviewResponse>(
        `/api/v1/attempts/${attemptId}/review`,
      );
      return res.data;
    },
    enabled: !!attemptId,
    staleTime: Infinity, // review data never changes once the attempt is COMPLETED
  });
}
