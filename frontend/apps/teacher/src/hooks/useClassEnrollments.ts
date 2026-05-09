import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface EnrolledStudent {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  worst_mastery: number | null;
  diagnostic_completed: boolean;
  grade_level: number | null;
}

export function useClassEnrollments(classId: string | undefined) {
  return useQuery<EnrolledStudent[]>({
    queryKey: ["teacher", "class-enrollments", classId] as const,
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}/enrollments`);
      return res.data ?? [];
    },
    enabled: !!classId,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
}
