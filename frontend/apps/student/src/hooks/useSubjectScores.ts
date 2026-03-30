/**
 * Hooks for fetching subject mastery scores via the gap-map API.
 *
 * Per STUDENT_SCREENS.md: Never construct student ID in URLs - always use /me shortcut.
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

/**
 * Interface for subject score data returned from gap-map aggregation.
 */
export interface SubjectScore {
  subjectId: string;
  subjectName: string;
  avgMastery: number | null; // null = no assessments yet for this subject
}

/**
 * Fetch gap-map data for a specific subject.
 *
 * @param subjectId - The UUID of the subject to fetch mastery data for
 * @returns Query result with gap-map data for the subject
 */
export const useSubjectGapMap = (subjectId: string | undefined) =>
  useQuery({
    queryKey: ["student", "gap-map", subjectId] as const,
    queryFn: () => {
      if (!subjectId) {
        throw new Error("subjectId is required");
      }
      return apiClient.get(`/api/v1/students/me/gap-map`, {
        params: { subject_id: subjectId },
      });
    },
    enabled: !!subjectId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

/**
 * Aggregate subject mastery from gap-map response data.
 *
 * Averages all non-null mastery scores across subtopics for a subject.
 * Returns null if no scores are available yet.
 *
 * @param gapMapData - The response from GET /students/me/gap-map?subject_id={id}
 * @returns Average mastery score (0-1) or null if no assessments exist
 */
export function aggregateSubjectMastery(gapMapData: any): number | null {
  if (!gapMapData?.scores || gapMapData.scores.length === 0) {
    return null;
  }

  const scores: number[] = gapMapData.scores
    .map((s: any) => s.mastery_score)
    .filter((v: any): v is number => v !== null && v !== undefined);

  if (scores.length === 0) {
    return null;
  }

  const sum = scores.reduce((acc: number, v: number) => acc + v, 0);
  return sum / scores.length;
}
