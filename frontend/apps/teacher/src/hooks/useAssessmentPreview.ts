import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface PreviewQuestion {
  question_id: string;
  question_text: string;
  question_type: string;
  options: Array<{ key: string; text: string }>;
  correct_answer_key: string;
  explanation: string | null;
  difficulty_level: number;
  subtopic_id: string;
  subtopic_name: string;
  topic_name: string;
  order_index: number;
  is_teacher_submitted: boolean;
}

export interface AssessmentPreview {
  id: string;
  class_id: string;
  title: string;
  assessment_type: string;
  status: string;
  question_count: number | null;
  questions_per_topic: number;
  minimum_difficulty: number;
  maximum_difficulty: number;
  time_limit_minutes: number;
  deadline: string | null;
  instructions: string | null;
  questions: PreviewQuestion[];
  attempt_count: number;
}

export interface ReplacementCandidate {
  question_id: string;
  question_text: string;
  question_type: string;
  options: Array<{ key: string; text: string }>;
  correct_answer_key: string;
  difficulty_level: number;
  subtopic_name: string;
  topic_name: string;
}

export interface AssessmentUpdatePayload {
  title?: string;
  instructions?: string | null;
  deadline?: string | null;
  question_count?: number;
  time_limit_minutes?: number;
  questions_per_topic?: number;
  minimum_difficulty?: number;
  maximum_difficulty?: number;
}

export interface AssessmentUpdateResponse extends AssessmentUpdatePayload {
  id: string;
  class_id: string;
  assessment_type: string;
  status: string;
  question_types: string[];
  created_at: string;
  published_at: string | null;
  has_attempts: boolean;
}

export function useAssessmentPreview(assessmentId: string | undefined) {
  return useQuery<AssessmentPreview>({
    queryKey: ["assessment", "preview", assessmentId],
    queryFn: async () => {
      const res = await apiClient.get<AssessmentPreview>(
        `/api/v1/assessments/${assessmentId}/preview`,
      );
      return res.data;
    },
    enabled: !!assessmentId,
  });
}

export function useUpdateAssessment(assessmentId: string, classId: string) {
  const queryClient = useQueryClient();
  return useMutation<AssessmentUpdateResponse, Error, AssessmentUpdatePayload>({
    mutationFn: async (payload) => {
      const res = await apiClient.patch<AssessmentUpdateResponse>(
        `/api/v1/assessments/${assessmentId}`,
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "preview", assessmentId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["assessments", "class", classId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["teacher", "assessments"],
      });
    },
  });
}
