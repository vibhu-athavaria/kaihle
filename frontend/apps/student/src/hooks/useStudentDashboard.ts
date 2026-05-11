import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types matching backend DashboardResponse ──────────────────────────────────

export type ActionItemType =
  | "assessment_due"
  | "lesson_pack_ready"
  | "study_plan_continue"
  | "diagnostic_pending";

export interface ActionItem {
  type: ActionItemType;
  class_id: string;
  class_name: string;
  subject_name: string;
  priority: number;
  due_date: string | null;
  action_url: string;
}

export interface ClassSummary {
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  subject_color: string;
  teacher_name: string;
  mastery_score: number | null;
  mastery_label: "Strong" | "Developing" | "Needs Work" | "Not assessed";
  topics_total: number;
  topics_assessed: number;
  diagnostic_status: "PENDING" | "IN_PROGRESS" | "COMPLETED";
  trend: "up" | "down" | "flat" | "none";
}

export interface DashboardData {
  student_name: string;
  grade: string;
  curriculum: string;
  action_items: ActionItem[];
  classes: ClassSummary[];
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useStudentDashboard() {
  return useQuery({
    queryKey: ["student", "dashboard"] as const,
    queryFn: async (): Promise<DashboardData> => {
      const res = await apiClient.get<DashboardData>(
        "/api/v1/students/me/dashboard",
      );
      return res.data;
    },
    staleTime: 2 * 60 * 1000,
  });
}
