import { useQuery } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";

/**
 * Response type for GET /api/v1/students/me/classes
 */
export interface StudentClassResponse {
  id: string;
  name: string; // e.g. "Mathematics 9B"
  subjectId: string;
  subjectName: string; // e.g. "Mathematics"
  gradeName: string; // e.g. "Grade 9"
  teacherName: string; // e.g. "Ms. Ravi"
  curriculumId: string;
  academicYear: string;
  isActive: boolean;
  onboardingDiagnosticStatus: "PENDING" | "IN_PROGRESS" | "COMPLETED";
  diagnosticAttemptId: string | null;
}

/**
 * Hook to fetch the current student's enrolled classes with full details.
 * Includes teacher name and diagnostic status for each class.
 */
export function useMyClasses() {
  // Include userId so different students on the same browser never share a cache entry.
  const userId = useAuthStore((state) => state.user?.id ?? null);
  return useQuery<StudentClassResponse[]>({
    queryKey: ["student", "classes", userId],
    queryFn: async () => {
      const response = await apiClient.get<StudentClassResponse[]>(
        "/api/v1/students/me/classes",
      );
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - class data doesn't change often
  });
}
