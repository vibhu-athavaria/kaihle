import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type { StudentGapMap } from "./useStudentProfile";

export function useStudentGapMapForTeacher(
  studentId: string | null,
  subjectId: string | null,
) {
  return useQuery<StudentGapMap>({
    queryKey: ["teacher", "student-gap-map", studentId, subjectId] as const,
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}/gap-map`, {
        params: { subject_id: subjectId },
      });
      return res.data;
    },
    enabled: !!studentId && !!subjectId,
    staleTime: 5 * 60 * 1000,
  });
}
