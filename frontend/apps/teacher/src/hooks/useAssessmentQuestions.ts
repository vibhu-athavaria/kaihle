import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type { ReplacementCandidate } from "./useAssessmentPreview";

export interface AddQuestionPayload {
  subtopic_id: string;
  question_text: string;
  question_type?: string;
  options?: Array<{ key: string; text: string }> | null;
  correct_answer: string;
  difficulty_level?: number;
  explanation?: string | null;
}

export interface AddQuestionResult {
  question_id: string;
  review_item_id: string;
  message: string;
}

export interface RemoveQuestionResult {
  removed: boolean;
  has_responses: boolean;
}

export interface ReplaceQuestionResult {
  replaced: boolean;
  has_responses_for_old: boolean;
}

export interface SuggestEditPayload {
  suggested_question_text?: string | null;
  suggested_options?: Array<{ key: string; text: string }> | null;
  suggested_correct_answer?: string | null;
  suggested_explanation?: string | null;
  suggested_difficulty_level?: number | null;
  reason: string;
}

export interface SuggestEditResult {
  review_item_id: string;
  message: string;
}

export interface ReplacementFilters {
  difficulty_level?: number;
  question_type?: string;
}

export function useAddQuestion(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation<AddQuestionResult, Error, AddQuestionPayload>({
    mutationFn: async (payload) => {
      const res = await apiClient.post<AddQuestionResult>(
        `/api/v1/assessments/${assessmentId}/questions`,
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "preview", assessmentId],
      });
    },
  });
}

export function useRemoveQuestion(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation<RemoveQuestionResult, Error, string>({
    mutationFn: async (questionId) => {
      const res = await apiClient.delete<RemoveQuestionResult>(
        `/api/v1/assessments/${assessmentId}/questions/${questionId}`,
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "preview", assessmentId],
      });
    },
  });
}

export function useReplacementCandidates(
  assessmentId: string,
  questionId: string | null,
  filters?: ReplacementFilters,
) {
  return useQuery<ReplacementCandidate[]>({
    queryKey: ["assessment", "replacements", assessmentId, questionId, filters],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (filters?.difficulty_level !== undefined)
        params.difficulty_level = String(filters.difficulty_level);
      if (filters?.question_type) params.question_type = filters.question_type;

      const res = await apiClient.get<ReplacementCandidate[]>(
        `/api/v1/assessments/${assessmentId}/questions/${questionId}/replacements`,
        { params },
      );
      return res.data;
    },
    enabled: !!assessmentId && !!questionId,
  });
}

export function useReplaceQuestion(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation<
    ReplaceQuestionResult,
    Error,
    { questionId: string; replacementQuestionId: string }
  >({
    mutationFn: async ({ questionId, replacementQuestionId }) => {
      const res = await apiClient.post<ReplaceQuestionResult>(
        `/api/v1/assessments/${assessmentId}/questions/${questionId}/replace`,
        { replacement_question_id: replacementQuestionId },
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "preview", assessmentId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "replacements", assessmentId],
      });
    },
  });
}

export function useSuggestEdit(assessmentId: string) {
  return useMutation<
    SuggestEditResult,
    Error,
    { questionId: string; payload: SuggestEditPayload }
  >({
    mutationFn: async ({ questionId, payload }) => {
      const res = await apiClient.post<SuggestEditResult>(
        `/api/v1/assessments/${assessmentId}/questions/${questionId}/suggest-edit`,
        payload,
      );
      return res.data;
    },
  });
}
