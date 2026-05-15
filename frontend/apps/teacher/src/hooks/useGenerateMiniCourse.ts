import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface GenerateMiniCourseResponse {
  task_id: string;
  status: string;
}

/**
 * POST /api/v1/topics/{topicId}/generate-course
 * Triggers async AI generation of mini-course content for all subtopics in a topic.
 * Returns a task_id and status "queued" — actual generation happens in the background.
 */
export function useGenerateMiniCourse() {
  return useMutation({
    mutationFn: async (
      topicId: string,
    ): Promise<GenerateMiniCourseResponse> => {
      const res = await apiClient.post(
        `/api/v1/topics/${topicId}/generate-course`,
      );
      return res.data as GenerateMiniCourseResponse;
    },
  });
}
