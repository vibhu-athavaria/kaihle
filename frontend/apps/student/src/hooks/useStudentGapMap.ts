import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface StudentSubtopicScore {
  subtopic_id: string;
  subtopic_name: string;
  topic_id: string;
  topic_name: string;
  mastery_score: number | null;
  last_assessed_at: string | null;
}

export interface StudentGapMap {
  student_id: string;
  subject_id: string;
  generated_at: string;
  scores: StudentSubtopicScore[];
}

export const useStudentGapMap = (subjectId: string | undefined) =>
  useQuery<StudentGapMap>({
    queryKey: ["student", "gap-map", subjectId] as const,
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/students/me/gap-map`, {
        params: { subject_id: subjectId },
      });
      return response.data;
    },
    enabled: !!subjectId,
    staleTime: 5 * 60 * 1000,
  });
