import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type SubtopicStatus = "not_started" | "in_progress" | "completed";

export interface SubtopicProgress {
  explanation_accessed: boolean;
  video_accessed: boolean;
  check_questions_score: number | null;
  status: SubtopicStatus;
}

export interface SubtopicItem {
  id: string;
  name: string;
  order: number;
  progress: SubtopicProgress | null;
}

export function useTopicSubtopics(classId: string, topicId: string) {
  return useQuery<SubtopicItem[]>({
    queryKey: ["student", "class-topic-subtopics", classId, topicId] as const,
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/classes/${classId}/topics/${topicId}/subtopics`,
      );
      return res.data ?? [];
    },
    enabled: !!classId && !!topicId,
    staleTime: 5 * 60 * 1000,
  });
}
