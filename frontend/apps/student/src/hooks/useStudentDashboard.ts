import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface Subject {
  subjectCode: string;
  subjectName: string;
  score: number | null;
}

interface GapMap {
  subjects: Subject[];
}

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

interface EnrolledClass {
  classId: string;
  className: string;
  subjectId: string;
  subjectName: string;
  gradeName: string;
}

interface StudentInfo {
  firstName: string;
  gradeName: string;
  curriculumName: string;
  classId?: string;
  isEnrolled: boolean;
  enrolledClasses: EnrolledClass[];
}

interface StudyPlansResponse {
  data: StudyPlan[];
}

interface DashboardData {
  gapMap: GapMap;
  studyPlans: StudyPlan[];
  assessments: Assessment[];
  studentInfo: StudentInfo;
}

/**
 * Fetches gap map data for the current student using /me endpoint.
 * Per STUDENT_SCREENS.md §4: Never construct student ID in URLs - always use /me shortcut.
 */
async function fetchGapMap(subjectId: string): Promise<GapMap> {
  const response = await apiClient.get<GapMap>(`/api/v1/students/me/gap-map`, {
    params: { subject_id: subjectId },
  });
  return response.data;
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

export function useStudentDashboard(): UseStudentDashboardResult {
  const studentInfoQuery = useQuery({
    queryKey: ["student", "info"] as const,
    queryFn: fetchStudentInfo,
  });

  // Get first enrolled class's subjectId for gap-map query
  const primarySubjectId =
    studentInfoQuery.data?.enrolledClasses?.[0]?.subjectId;

  const gapMapQuery = useQuery({
    queryKey: ["student", "gap-map", primarySubjectId] as const,
    queryFn: () => {
      if (!primarySubjectId) throw new Error("Subject ID not available");
      return fetchGapMap(primarySubjectId);
    },
    // Only fetch gap-map if student has a subject
    enabled: !!primarySubjectId,
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
    gapMapQuery.isPending ||
    studyPlansQuery.isPending ||
    assessmentsQuery.isPending ||
    studentInfoQuery.isPending;

  const isError =
    gapMapQuery.isError ||
    studyPlansQuery.isError ||
    assessmentsQuery.isError ||
    studentInfoQuery.isError;

  const errMessage =
    gapMapQuery.error?.message ||
    studyPlansQuery.error?.message ||
    assessmentsQuery.error?.message ||
    studentInfoQuery.error?.message;

  const data = studentInfoQuery.data
    ? {
        gapMap: gapMapQuery.data || { subjects: [] },
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
      await gapMapQuery.refetch();
      await studyPlansQuery.refetch();
      await assessmentsQuery.refetch();
      await studentInfoQuery.refetch();
    },
  };
}
