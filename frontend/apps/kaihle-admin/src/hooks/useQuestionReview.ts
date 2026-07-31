import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type ReviewItemType = "TEACHER_QUESTION" | "EDIT_SUGGESTION";

export interface QuestionReviewItem {
  id: string;
  item_type: ReviewItemType;
  question_id: string;
  question_text: string;
  question_type: string;
  options: Array<{ key: string; text: string }> | null;
  correct_answer: string;
  explanation: string | null;
  difficulty_level: number | null;
  subtopic_name: string;
  topic_name: string;
  school_name: string;
  submitted_by_name: string;
  assessment_id: string | null;
  suggested_question_text: string | null;
  suggested_options: Array<{ key: string; text: string }> | null;
  suggested_correct_answer: string | null;
  suggested_explanation: string | null;
  suggested_difficulty_level: number | null;
  reason: string | null;
  status: string;
  admin_note: string | null;
  created_at: string;
}

export interface QuestionReviewListResponse {
  items: QuestionReviewItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApprovePayload {
  question_text?: string;
  options?: Array<{ key: string; text: string }>;
  correct_answer?: string;
  explanation?: string;
  difficulty_level?: number;
}

export interface RejectPayload {
  admin_note?: string;
}

const BASE = "/api/v1/question-review-items";

export function useQuestionReviewItems(
  itemType: ReviewItemType | undefined,
  page: number,
) {
  return useQuery<QuestionReviewListResponse>({
    queryKey: ["question-review-items", itemType, page],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (itemType) params.item_type = itemType;
      const res = await apiClient.get<QuestionReviewListResponse>(BASE, {
        params,
      });
      return res.data;
    },
  });
}

export function useApproveReviewItem() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { itemId: string; payload?: ApprovePayload }>(
    {
      mutationFn: async ({ itemId, payload }) => {
        await apiClient.post(`${BASE}/${itemId}/approve`, payload ?? {});
      },
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: ["question-review-items"],
        });
      },
    },
  );
}

export function useRejectReviewItem() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { itemId: string; payload?: RejectPayload }>({
    mutationFn: async ({ itemId, payload }) => {
      await apiClient.post(`${BASE}/${itemId}/reject`, payload ?? {});
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["question-review-items"],
      });
    },
  });
}
