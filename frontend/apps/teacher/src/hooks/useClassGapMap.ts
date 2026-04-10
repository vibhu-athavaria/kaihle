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
    staleTime: 5 * 60 * 1000,
  });
