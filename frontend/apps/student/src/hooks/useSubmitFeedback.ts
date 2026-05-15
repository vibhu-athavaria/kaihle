import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type { FeedbackPayload } from "../types/miniCourse";

interface FeedbackResponse {
  id: string;
  feedback_type: "thumbs_up" | "thumbs_down";
  comment: string | null;
  created_at: string;
}

export function useSubmitFeedback(contentId: string, subtopicId: string) {
  const queryClient = useQueryClient();

  return useMutation<FeedbackResponse, Error, FeedbackPayload>({
    mutationFn: async (payload: FeedbackPayload) => {
      const response = await apiClient.post<FeedbackResponse>(
        `/api/v1/students/me/subtopic-content/${contentId}/feedback`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["subtopic-course", subtopicId],
      });
    },
  });
}
