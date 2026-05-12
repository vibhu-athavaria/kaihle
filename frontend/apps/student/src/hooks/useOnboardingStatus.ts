import { useQuery } from "@tanstack/react-query";
import { apiClient, useAuth } from "@kaihle/auth";

export interface DiagnosticStatusByClass {
  class_id: string;
  class_name: string;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED";
}

export type OnboardingStatus = {
  learning_profile_complete: boolean;
};

export function useOnboardingStatus() {
  const { user } = useAuth();

  return useQuery<OnboardingStatus>({
    queryKey: ["student", "onboarding-status", user?.id],
    queryFn: async () => {
      const res = await apiClient.get<OnboardingStatus>(
        `/api/v1/onboarding/status/${user!.id}`,
      );
      return res.data;
    },
    enabled: !!user?.id,
    staleTime: 30 * 1000, // 30s — re-check frequently during onboarding
    refetchOnWindowFocus: true, // refetch when student tabs back in
  });
}
