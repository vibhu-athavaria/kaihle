import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { type StudentInfo } from "./useStudentInfo";

interface StudyPlan {
  id: string;
  title: string;
  status: "ACTIVE" | "IN_PROGRESS" | "COMPLETED";
}

interface Assessment {
  id: string;
  subjectName: string;
  dueDate: string;
}

interface StudyPlansResponse {
  data: StudyPlan[];
}

interface DashboardData {
  studyPlans: StudyPlan[];
  assessments: Assessment[];
  studentInfo: StudentInfo;
}

/**
 * Fetches study plans for the current student using /me endpoint.
 * Per STUDENT_SCREENS.md §4: Never construct student ID in URLs - always use /me shortcut.
 */
async function fetchStudyPlans(): Promise<StudyPlan[]> {
  const response = await apiClient.get<StudyPlansResponse>(
    `/api/v1/students/me/study-plans?status=active,in_progress&limit=10`,
  );
  return response.data.data;
}

/**
 * Fetches assessments for a given class using /me shortcut for student context.
 * Per STUDENT_SCREENS.md §4: Never construct student ID in URLs - always use /me shortcut.
 * Note: classId is still needed for the class-specific assessments endpoint.
 */
async function fetchAssessments(classId: string): Promise<Assessment[]> {
  const response = await apiClient.get<Assessment[]>(
    `/api/v1/classes/${classId}/assessments?status=ACTIVE&limit=5`,
  );
  return response.data;
}

/**
 * Fetches student info for the current student using /me endpoint.
 * Per STUDENT_SCREENS.md §4: Never construct student ID in URLs - always use /me shortcut.
 */
async function fetchStudentInfo(): Promise<StudentInfo> {
  const response = await apiClient.get<StudentInfo>(`/api/v1/students/me/info`);
  return response.data;
}

interface UseStudentDashboardResult {
  data: DashboardData | undefined;
  isPending: boolean;
  isError: boolean;
  errMessage: string | undefined;
  refetch: () => Promise<void>;
}

/**
 * Fetches all data needed for the student dashboard.
 *
 * Per-subject gap maps are NOT fetched here — SubjectScoresSection fetches
 * them independently via useStudentGapMap per subject. Fetching a single
 * subject's gap map here (hardcoded to [0]) was redundant and only worked
 * for single-subject students.
 */
export function useStudentDashboard(): UseStudentDashboardResult {
  const studentInfoQuery = useQuery({
    queryKey: ["student", "info"] as const,
    queryFn: fetchStudentInfo,
  });

  const studyPlansQuery = useQuery({
    queryKey: ["student", "study-plans"] as const,
    queryFn: fetchStudyPlans,
    // Only fetch study plans if student is enrolled
    enabled: studentInfoQuery.data?.isEnrolled === true,
  });

  const assessmentsQuery = useQuery({
    queryKey: [
      "student",
      "assessments",
      studentInfoQuery.data?.classId,
    ] as const,
    queryFn: () => {
      const classId = studentInfoQuery.data?.classId;
      if (!classId) throw new Error("Class ID not available");
      return fetchAssessments(classId);
    },
    enabled: !!studentInfoQuery.data?.classId,
  });

  const isPending =
    studyPlansQuery.isPending ||
    assessmentsQuery.isPending ||
    studentInfoQuery.isPending;

  const isError =
    studyPlansQuery.isError ||
    assessmentsQuery.isError ||
    studentInfoQuery.isError;

  const errMessage =
    studyPlansQuery.error?.message ||
    assessmentsQuery.error?.message ||
    studentInfoQuery.error?.message;

  const data = studentInfoQuery.data
    ? {
        studyPlans: studyPlansQuery.data || [],
        assessments: assessmentsQuery.data || [],
        studentInfo: studentInfoQuery.data,
      }
    : undefined;

  return {
    data,
    isPending,
    isError,
    errMessage,
    refetch: async () => {
      // Parallel refetch — was serial before (ST-005), took 4–8s on mobile
      await Promise.all([
        studyPlansQuery.refetch(),
        assessmentsQuery.refetch(),
        studentInfoQuery.refetch(),
      ]);
    },
  };
}
