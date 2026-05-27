import { useQuery } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";

/**
 * Response type for GET /api/v1/students/me/info
 * Uses camelCase to match backend Pydantic field aliases (alias="firstName", etc.)
 */
export interface EnrolledClass {
  classId: string;
  className: string;
  subjectId: string;
  subjectName: string;
  gradeName: string;
}

export interface StudentInfo {
  id: string;
  firstName: string;
  lastName?: string;
  email: string;
  gradeName: string;
  curriculumName: string;
  schoolId: string;
  classId?: string | null;
  isEnrolled?: boolean;
  enrolledClasses: EnrolledClass[];
}

/**
 * Hook to fetch the current student's identity information.
 * Includes name, grade, curriculum, and school ID.
 */
export function useStudentInfo() {
  // Include userId so different students on the same browser never share a cache entry.
  const userId = useAuthStore((state) => state.user?.id ?? null);
  return useQuery<StudentInfo>({
    queryKey: ["student", "info", userId],
    queryFn: async () => {
      const response = await apiClient.get<StudentInfo>(
        "/api/v1/students/me/info",
      );
      return response.data;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - student info rarely changes
  });
}
