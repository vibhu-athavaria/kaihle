import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ---------------------------------------------------------------------------
// Concept Explanation
// ---------------------------------------------------------------------------

export interface ConceptExplanationRequest {
  subtopic_id: string;
  student_id?: string;
  question?: string;
}

export interface ConceptExplanationResult {
  subtopic_name: string;
  modality_used: string;
  has_profile: boolean;
  explanation: string;
  check_question: {
    question: string;
    options: string[];
    correct: string;
  } | null;
  duration_ms: number;
}

export function useSmokeTestConceptExplanation() {
  return useMutation({
    mutationFn: async (req: ConceptExplanationRequest) => {
      const response = await apiClient.post<ConceptExplanationResult>(
        "/api/v1/smoke-tests/concept-explanation",
        req,
      );
      return response.data;
    },
  });
}

// ---------------------------------------------------------------------------
// Mini-Course
// ---------------------------------------------------------------------------

export interface MiniCourseRequest {
  topic_id: string;
  school_id: string;
  dry_run: boolean;
}

export interface MiniCourseResult {
  topic_name: string | null;
  subtopics_found: number;
  subtopics_processed: number;
  explanations_written: number;
  dry_run: boolean;
  dry_run_results: Array<{
    subtopic_name: string;
    interest_category: string;
    interest_label: string;
    explanation_text: string;
  }>;
  duration_ms: number;
}

export function useSmokeTestMiniCourse() {
  return useMutation({
    mutationFn: async (req: MiniCourseRequest) => {
      const response = await apiClient.post<MiniCourseResult>(
        "/api/v1/smoke-tests/mini-course",
        req,
      );
      return response.data;
    },
  });
}

// ---------------------------------------------------------------------------
// Lesson Plan
// ---------------------------------------------------------------------------

export interface LessonPlanRequest {
  class_id: string;
  focus_subtopic_ids: string[];
  duration_minutes: number;
  dry_run: boolean;
}

export interface LessonPlanResult {
  class_name: string;
  subject_name: string;
  grade_name: string;
  student_count: number;
  modality_distribution: Record<string, number>;
  top_interests: string[];
  validation_passed: boolean;
  generated_plan: Record<string, unknown> | null;
  raw_llm_output: string | null;
  error: string | null;
  llm_calls: number;
  duration_ms: number;
}

export function useSmokeTestLessonPlan() {
  return useMutation({
    mutationFn: async (req: LessonPlanRequest) => {
      const response = await apiClient.post<LessonPlanResult>(
        "/api/v1/smoke-tests/lesson-plan",
        req,
      );
      return response.data;
    },
  });
}

// ---------------------------------------------------------------------------
// Practice Quiz
// ---------------------------------------------------------------------------

export interface PracticeQuizRequest {
  subtopic_id: string;
  mastery_score: number;
  student_id?: string;
}

export interface PracticeQuizResult {
  subtopic_name: string;
  difficulty_label: string;
  interests_used: string[];
  explanation_context_found: boolean;
  question_count: number;
  questions: Array<{
    question_text: string;
    type: string;
    options: Array<{ key: string; text: string }>;
    correct_answer: string;
    explanation: string;
  }>;
  duration_ms: number;
}

export function useSmokeTestPracticeQuiz() {
  return useMutation({
    mutationFn: async (req: PracticeQuizRequest) => {
      const response = await apiClient.post<PracticeQuizResult>(
        "/api/v1/smoke-tests/practice-quiz",
        req,
      );
      return response.data;
    },
  });
}
