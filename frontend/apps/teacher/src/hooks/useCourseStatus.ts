import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type MiniCourseStatus = "none" | "generating" | "ready" | "failed";

export interface CourseStatusResponse {
  status: MiniCourseStatus;
  subtopic_count: number;
}

/**
 * GET /api/v1/topics/{topicId}/course-status
 * Polls the mini-course generation status for a topic.
 */
export function useCourseStatus(topicId: string | null) {
  return useQuery<CourseStatusResponse>({
    queryKey: ["course-status", topicId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/topics/${topicId}/course-status`,
      );
      return res.data as CourseStatusResponse;
    },
    enabled: !!topicId,
    // State only changes via explicit user action (invalidated manually) or
    // during generation (polled via refetchInterval below). Window-focus
    // refetch adds no value and fires constantly when devtools are open.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      // Poll every 5s while generating, stop once settled
      const data = query.state.data;
      return data?.status === "generating" ? 5_000 : false;
    },
  });
}
