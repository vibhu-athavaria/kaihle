import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

/**
 * GET /api/v1/teachers/me/explanation-review?status=pending
 * Returns the count of mini-course content items awaiting this teacher's review, for the
 * sidebar's "Content Review" badge. Used only by the sidebar — per
 * .claude/rules/13-frontend-api-discipline.md, no other page should reuse this hook for
 * anything beyond the badge count.
 */
export function usePendingReviewCount() {
  return useQuery<number>({
    queryKey: ["pending-review-count"],
    queryFn: async () => {
      const res = await apiClient.get<unknown[]>(
        "/api/v1/teachers/me/explanation-review?status=pending",
      );
      return res.data.length;
    },
    staleTime: 60_000,
  });
}
