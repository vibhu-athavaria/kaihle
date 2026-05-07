import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface Topic {
  id: string;
  name: string;
  description: string | null;
}

export function useClassTopics(classId: string) {
  return useQuery<Topic[]>({
    queryKey: ["class", classId, "topics"],
    queryFn: async () => {
      const response = await apiClient.get<Topic[]>(
        `/api/v1/classes/${classId}/topics`,
      );
      return response.data;
    },
    enabled: !!classId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
