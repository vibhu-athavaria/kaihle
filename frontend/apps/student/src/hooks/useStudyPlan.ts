import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type { StudyPlanSummary } from "./useMyStudyPlans";

export function useStudyPlan(planId: string | undefined) {
  return useQuery<StudyPlanSummary>({
    queryKey: ["student", "study-plan", planId],
    queryFn: async () => {
      const response = await apiClient.get<StudyPlanSummary>(
        `/api/v1/study-plans/${planId}`,
      );
      return response.data;
    },
    enabled: !!planId,
    staleTime: 2 * 60 * 1000,
  });
}
