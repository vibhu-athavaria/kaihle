import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface TopicAvailability {
  curriculum_topic_id: string;
  topic_name: string;
  grade_level: number;
  available_questions: number;
  per_difficulty_available: Record<number, number>;
  fulfillable: boolean;
}

interface UseTopicAvailabilityParams {
  classId: string;
  topicIds: string[];
  questionsPerTopic: number;
  minimumDifficulty: number;
  maximumDifficulty: number;
  questionTypes: string[];
}

export function useTopicAvailability({
  classId,
  topicIds,
  questionsPerTopic,
  minimumDifficulty,
  maximumDifficulty,
  questionTypes,
}: UseTopicAvailabilityParams) {
  return useQuery<TopicAvailability[]>({
    queryKey: [
      "topic-availability",
      classId,
      topicIds,
      questionsPerTopic,
      minimumDifficulty,
      maximumDifficulty,
      questionTypes,
    ],
    queryFn: async () => {
      const res = await apiClient.post(
        `/api/v1/classes/${classId}/assessments/topic-availability`,
        {
          topic_ids: topicIds,
          questions_per_topic: questionsPerTopic,
          minimum_difficulty: minimumDifficulty,
          maximum_difficulty: maximumDifficulty,
          question_types: questionTypes,
        },
      );
      return res.data as TopicAvailability[];
    },
    enabled: topicIds.length > 0,
    staleTime: 30_000,
  });
}
