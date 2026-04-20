import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface StudyPlanResource {
  resource_id: string;
  title: string;
  resource_type: string; // "VIDEO" | "ARTICLE" | "INTERACTIVE"
  url: string;
  source: string; // "YOUTUBE" | "KAIHLE"
  duration_minutes: number | null;
  is_watched: boolean;
}

export interface StudyPlanQuizQuestion {
  question_index: number;
  question_text: string;
  options: Array<{ key: string; text: string }>;
}

export interface StudyPlanSummary {
  id: string;
  student_id: string;
  class_id: string;
  subtopic_id: string;
  subtopic_name: string;
  status: "GENERATING" | "ACTIVE" | "IN_PROGRESS" | "COMPLETED" | "ABANDONED";
  resources: StudyPlanResource[];
  quiz_questions: StudyPlanQuizQuestion[];
  quiz_score: number | null;
  created_at: string;
}

interface StudyPlansPage {
  data: StudyPlanSummary[];
  total: number;
  page: number;
  page_size: number;
}

export function useMyStudyPlans(statusFilter?: string) {
  return useQuery<StudyPlansPage>({
    queryKey: ["student", "study-plans", statusFilter],
    queryFn: async () => {
      const params: Record<string, string> = { page: "1", page_size: "20" };
      if (statusFilter) params.status = statusFilter;
      const response = await apiClient.get<StudyPlansPage>(
        "/api/v1/students/me/study-plans",
        { params },
      );
      return response.data;
    },
    staleTime: 2 * 60 * 1000,
  });
}
