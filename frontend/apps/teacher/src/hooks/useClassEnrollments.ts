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
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      // Poll every 30 s while any student is still awaiting their diagnostic,
      // so the teacher sees completion updates without a manual refresh.
      const data = query.state.data as EnrolledStudent[] | undefined;
      if (!data) return false;
      const hasPending = data.some((s) => !s.diagnostic_completed);
      return hasPending ? 30_000 : false;
    },
  });
}
