import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface SubtopicProgressItem {
  subtopic_id: string;
  subtopic_name: string;
  topic_name: string;
  last_visited_at: string;
  explanation_accessed: boolean;
  video_accessed: boolean;
  check_questions_score: number | null;
}

export interface StudentMiniCourseProgress {
  student_id: string;
  progress: SubtopicProgressItem[];
}

export function useStudentMiniCourseProgress(studentId: string | null) {
  return useQuery<StudentMiniCourseProgress>({
    queryKey: ["teacher", "student-mini-course-progress", studentId] as const,
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/students/${studentId}/mini-course-progress`,
      );
      return res.data;
    },
    enabled: !!studentId,
    staleTime: 2 * 60 * 1000,
  });
}
