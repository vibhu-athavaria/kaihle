import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export const useClassGapMap = (
  classId: string | null,
  subjectId: string | null,
) =>
  useQuery({
    queryKey: ["teacher", "class-gap-map", classId, subjectId] as const,
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/v1/classes/${classId}/gap-map`,
        {
          params: { subject_id: subjectId },
        },
      );
      return response.data;
    },
    enabled: !!classId && !!subjectId,
    staleTime: 15_000,
    refetchInterval: (query) => {
      return query.state.data?.has_student_data ? false : 15_000;
    },
  });
