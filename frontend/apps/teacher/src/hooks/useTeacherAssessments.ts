import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";

export type AssessmentStatus = "DRAFT" | "ACTIVE" | "CLOSED";

export interface TeacherAssessment {
  id: string;
  classId: string;
  className: string;
  gradeName: string;
  title: string;
  assessment_type: string;
  is_system_generated: boolean;
  status: AssessmentStatus;
  question_count: number;
  created_at: string;
  published_at: string | null;
  deadline: string | null;
}

interface AssessmentWithClassResponse {
  id: string;
  class_id: string;
  class_name: string;
  grade_name: string;
  title: string;
  assessment_type: string;
  is_system_generated: boolean;
  status: string;
  topic_ids: string[];
  question_count: number;
  created_at: string;
  published_at: string | null;
  deadline: string | null;
}

async function fetchTeacherAssessments(
  status?: AssessmentStatus,
): Promise<TeacherAssessment[]> {
  const params: Record<string, string> = {};
  if (status) {
    params.status = status;
  }
  const res = await apiClient.get<AssessmentWithClassResponse[]>(
    `/api/v1/teachers/me/assessments`,
    { params },
  );
  return (res.data ?? []).map((a) => ({
    id: a.id,
    classId: a.class_id,
    className: a.class_name,
    gradeName: a.grade_name,
    title: a.title,
    assessment_type: a.assessment_type,
    is_system_generated: a.is_system_generated,
    status: a.status as AssessmentStatus,
    question_count: a.question_count,
    created_at: a.created_at,
    published_at: a.published_at,
    deadline: a.deadline,
  }));
}

export function useTeacherAssessments(status?: AssessmentStatus) {
  // Include userId so teachers in the same school never share a cache entry.
  const userId = useAuthStore((state) => state.user?.id ?? null);
  return useQuery({
    queryKey: ["teacher", "assessments", status, userId],
    queryFn: () => fetchTeacherAssessments(status),
    staleTime: 30 * 1000,
  });
}

export function useCloseTeacherAssessment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assessmentId: string) =>
      apiClient.post(`/api/v1/assessments/${assessmentId}/close`),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["teacher", "assessments"],
      });
    },
  });
}

export function useDeleteTeacherAssessment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assessmentId: string) =>
      apiClient.delete(`/api/v1/assessments/${assessmentId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["teacher", "assessments"],
      });
    },
  });
}
