import { useQuery } from "@tanstack/react-query";
import apiClient from "axios";

/**
 * Response type for GET /api/v1/students/me/info
 */
export interface StudentInfo {
  id: string;
  first_name: string;
  last_name: string;
  grade_name: string; // e.g. "Grade 9"
  curriculum_name: string; // e.g. "Cambridge IGCSE"
  school_id: string;
}

/**
 * Hook to fetch the current student's identity information.
 * Includes name, grade, curriculum, and school ID.
 */
export function useStudentInfo() {
  return useQuery<StudentInfo>({
    queryKey: ["student", "info"],
    queryFn: async () => {
      const response = await apiClient.get<StudentInfo>(
        "/api/v1/students/me/info",
      );
      return response.data;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - student info rarely changes
  });
}
