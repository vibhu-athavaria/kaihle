import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type AttemptStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";

export interface MyAssessmentItem {
  id: string;
  classId: string;
  className: string;
  title: string;
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK";
  status: "ACTIVE" | "CLOSED";
  questionCount: number | null;
  deadline: string | null;
  publishedAt: string | null;
  attemptStatus: AttemptStatus;
  attemptId: string | null;
  score: number | null;
}

/**
 * Fetches all assessments across the student's active enrolled classes.
 * Shared query key ["student", "assessments"] — React Query deduplicates
 * this across every page that mounts it (Assessments page + sidebar badge).
 */
export function useMyAssessments() {
  return useQuery<MyAssessmentItem[]>({
    queryKey: ["student", "assessments"],
    queryFn: async () => {
      const res = await apiClient.get<MyAssessmentItem[]>(
        "/api/v1/students/me/assessments",
      );
      return res.data;
    },
    staleTime: 2 * 60 * 1000,
  });
}
