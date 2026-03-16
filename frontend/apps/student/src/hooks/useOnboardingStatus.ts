import { useEffect, useState } from "react";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";

export type OnboardingStatus = {
  learning_profile_complete: boolean;
  diagnostics_by_class: Array<{
    class_id: string;
    class_name: string;
    status: "PENDING" | "IN_PROGRESS" | "COMPLETED";
  }>;
};

interface UseOnboardingStatusResult {
  status: OnboardingStatus | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useOnboardingStatus(): UseOnboardingStatusResult {
  const { user } = useAuth();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchStatus = async () => {
    if (!user?.id) return;

    try {
      setIsLoading(true);
      const response = await apiClient.get<OnboardingStatus>(
        `/api/v1/onboarding/status/${user.id}`,
      );
      setStatus(response.data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err
          : new Error("Failed to fetch onboarding status"),
      );
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();

    const handleFocus = () => {
      fetchStatus();
    };

    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [user?.id]);

  return { status, isLoading, error, refetch: fetchStatus };
}
