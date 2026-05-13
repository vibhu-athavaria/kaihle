import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface DiagnosticTopicItem {
  curriculum_topic_id: string;
  topic_name: string;
  grade_level: number;
  subtopic_count: number;
}

export interface ClassTopicsWithGrades {
  current_grade_level: number;
  previous_grade_level: number;
  current_grade_topics: DiagnosticTopicItem[];
  previous_grade_topics: DiagnosticTopicItem[];
}

export function useClassTopicsWithGrades(classId: string | undefined) {
  return useQuery<ClassTopicsWithGrades>({
    queryKey: ["class", classId, "topics-diagnostic"],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/classes/${classId}/topics/diagnostic`,
      );
      return res.data as ClassTopicsWithGrades;
    },
    enabled: !!classId,
  });
}
