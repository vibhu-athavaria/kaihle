import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface ClassDetail {
  id: string;
  name: string;
  grade_id: string;
  subject_id: string;
  subject_name: string;
  curriculum_id: string;
  is_active: boolean;
}

export function useClass(classId: string | undefined) {
  return useQuery<ClassDetail>({
    queryKey: ["class", classId] as const,
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}`);
      return res.data as ClassDetail;
    },
    enabled: !!classId,
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
