import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type { Topic } from "@kaihle/types";

export type { Topic };

// Shape returned by GET /api/v1/classes/{classId}/topics (class_topics router)
interface ClassTopicApiResponse {
  id: string;
  class_id: string;
  curriculum_topic_id: string;
  topic_id: string;
  sequence_order: number;
  is_covered: boolean;
  topic_name: string;
  subtopic_count: number;
}

export function useClassTopics(classId: string) {
  return useQuery<Topic[]>({
    queryKey: ["class", classId, "topics"],
    queryFn: async () => {
      const response = await apiClient.get<ClassTopicApiResponse[]>(
        `/api/v1/classes/${classId}/topics`,
      );
      return response.data.map((t) => ({
        id: t.id, // class_topic id — used by topic detail route
        name: t.topic_name,
        description: null,
      }));
    },
    enabled: !!classId,
    staleTime: 5 * 60 * 1000,
  });
}
