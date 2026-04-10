import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type AssessmentStatus = "DRAFT" | "ACTIVE" | "CLOSED";

export interface Assessment {
  id: string;
  title: string;
  assessment_type: string;
  status: AssessmentStatus;
  question_count: number;
  deadline: string | null;
  created_at: string;
}

async function fetchClassAssessments(classId: string): Promise<Assessment[]> {
  const res = await apiClient.get(`/api/v1/classes/${classId}/assessments`);
  return res.data || [];
}

async function publishAssessment(assessmentId: string): Promise<void> {
  await apiClient.post(`/api/v1/assessments/${assessmentId}/publish`);
}

async function closeAssessment(assessmentId: string): Promise<void> {
  await apiClient.post(`/api/v1/assessments/${assessmentId}/close`);
}

async function deleteAssessment(assessmentId: string): Promise<void> {
  await apiClient.delete(`/api/v1/assessments/${assessmentId}`);
}

export function useClassAssessments(classId: string | undefined) {
  return useQuery({
    queryKey: ["assessments", "class", classId],
    queryFn: () => fetchClassAssessments(classId!),
    enabled: !!classId,
  });
}

export function usePublishAssessment(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: publishAssessment,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessments", "class", classId],
      });
    },
  });
}

export function useCloseAssessment(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: closeAssessment,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessments", "class", classId],
      });
    },
  });
}

export function useDeleteAssessment(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAssessment,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["assessments", "class", classId],
      });
    },
  });
}
