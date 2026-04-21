import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface MarkWatchedVars {
  planId: string;
  resourceId: string;
}

export function useMarkResourceWatched() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, MarkWatchedVars>({
    mutationFn: async ({ planId, resourceId }) => {
      await apiClient.patch(
        `/api/v1/study-plans/${planId}/resources/${resourceId}/watched`,
      );
    },
    onSuccess: (_, { planId }) => {
      queryClient.invalidateQueries({
        queryKey: ["student", "study-plan", planId],
      });
      queryClient.invalidateQueries({ queryKey: ["student", "study-plans"] });
    },
  });
}
