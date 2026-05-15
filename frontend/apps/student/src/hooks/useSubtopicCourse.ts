import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type {
  SubtopicCourse,
  MarkProgressPayload,
  FeedbackPayload,
} from "../types/miniCourse";

export function useSubtopicCourse(subtopicId: string) {
  return useQuery<SubtopicCourse>({
    queryKey: ["subtopic-course", subtopicId],
    queryFn: async () => {
      const response = await apiClient.get<SubtopicCourse>(
        `/api/v1/students/me/subtopics/${subtopicId}/course`,
      );
      return response.data;
    },
    enabled: !!subtopicId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

export function useMarkCourseProgress(subtopicId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MarkProgressPayload) => {
      const response = await apiClient.post(
        `/api/v1/students/me/subtopics/${subtopicId}/course/progress`,
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

export function useSubmitFeedback(contentId: string) {
  return useMutation({
    mutationFn: async (payload: FeedbackPayload) => {
      const response = await apiClient.post(
        `/api/v1/students/me/subtopic-content/${contentId}/feedback`,
        payload,
      );
      return response.data;
    },
  });
}
