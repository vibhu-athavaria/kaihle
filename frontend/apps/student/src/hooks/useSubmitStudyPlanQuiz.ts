import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface QuizResponse {
  question_index: number;
  answer: string;
}

interface QuizSubmitRequest {
  responses: QuizResponse[];
}

export interface QuizResult {
  score: number;
  correct_count: number;
  total_questions: number;
  plan_status: string;
}

export function useSubmitStudyPlanQuiz(planId: string) {
  const queryClient = useQueryClient();

  return useMutation<QuizResult, Error, QuizSubmitRequest>({
    mutationFn: async (body) => {
      const response = await apiClient.post<QuizResult>(
        `/api/v1/study-plans/${planId}/quiz`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["student", "study-plan", planId] });
      queryClient.invalidateQueries({ queryKey: ["student", "study-plans"] });
    },
  });
}
