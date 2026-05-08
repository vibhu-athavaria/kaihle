import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type { TopicDetail } from "@kaihle/types";

export type { TopicDetail };

export function useTopicDetail(classId: string, topicId: string) {
  return useQuery<TopicDetail>({
    queryKey: ["class", classId, "topic", topicId],
    queryFn: async () => {
      const response = await apiClient.get<TopicDetail>(
        `/api/v1/classes/${classId}/topics/${topicId}`,
      );
      return response.data;
    },
    enabled: !!classId && !!topicId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
