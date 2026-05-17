import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface TeacherStudent {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  grade_name: string | null;
  class_ids: string[];
  class_names: string[];
}

interface TeacherStudentsResponse {
  students: TeacherStudent[];
}

export function useTeacherStudents(schoolId: string | null) {
  return useQuery({
    queryKey: ["teacher", "students", schoolId] as const,
    queryFn: async (): Promise<TeacherStudent[]> => {
      const res = await apiClient.get<TeacherStudentsResponse>(
        "/api/v1/teachers/me/students",
      );
      return res.data.students ?? [];
    },
    enabled: !!schoolId,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
}
