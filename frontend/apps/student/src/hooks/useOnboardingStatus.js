import { useEffect, useState, useRef } from "react";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";
export function useOnboardingStatus() {
    const { user } = useAuth();
    const [status, setStatus] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const isInitialFetch = useRef(true);
    const fetchStatus = async (isRefetch = false) => {
        if (!user?.id)
            return;
        try {
            // Only show loading on initial fetch, not on refetch
            if (isInitialFetch.current) {
                setIsLoading(true);
                isInitialFetch.current = false;
            }
            const response = await apiClient.get(`/api/v1/onboarding/status/${user.id}`);
            setStatus(response.data);
            setError(null);
        }
        catch (err) {
            setError(err instanceof Error
                ? err
                : new Error("Failed to fetch onboarding status"));
            setStatus(null);
        }
        finally {
            if (!isRefetch) {
                setIsLoading(false);
            }
        }
    };
    useEffect(() => {
        fetchStatus();
        const handleFocus = () => {
            fetchStatus(true); // true = isRefetch
        };
        window.addEventListener("focus", handleFocus);
        return () => window.removeEventListener("focus", handleFocus);
    }, [user?.id]);
    return { status, isLoading, error, refetch: () => fetchStatus(true) };
}
