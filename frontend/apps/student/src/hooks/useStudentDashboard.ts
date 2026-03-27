import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";

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
  streakDays?: number;
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

const QUERY_KEYS = {
  dashboard: (studentId: string) =>
    ["student", "dashboard", studentId] as const,
  gapMap: (studentId: string) => ["student", "gap-map", studentId] as const,
};

async function fetchGapMap(
  studentId: string,
  subjectId: string,
): Promise<GapMap> {
  const response = await apiClient.get<GapMap>(
    `/api/v1/students/${studentId}/gap-map`,
    {
      params: { subject_id: subjectId },
    },
  );
  return response.data;
}

async function fetchStudyPlans(studentId: string): Promise<StudyPlan[]> {
  const response = await apiClient.get<StudyPlansResponse>(
    `/api/v1/students/${studentId}/study-plans?status=active,in_progress&limit=10`,
  );
  return response.data.data;
}

async function fetchAssessments(classId: string): Promise<Assessment[]> {
  const response = await apiClient.get<Assessment[]>(
    `/api/v1/classes/${classId}/assessments?status=ACTIVE&limit=5`,
  );
  return response.data;
}

async function fetchStudentInfo(studentId: string): Promise<StudentInfo> {
  const response = await apiClient.get<StudentInfo>(
    `/api/v1/students/${studentId}/info`,
  );
  return response.data;
}

interface UseStudentDashboardResult {
  data: DashboardData | undefined;
  isLoading: boolean;
  isError: boolean;
  errMessage: string | undefined;
  refetch: () => Promise<void>;
}

export function useStudentDashboard(): UseStudentDashboardResult {
  const { user } = useAuth();

  const studentInfoQuery = useQuery({
    queryKey: ["student", "info", user?.id] as const,
    queryFn: () => {
      if (!user?.id) throw new Error("User ID not available");
      return fetchStudentInfo(user.id);
    },
    enabled: !!user?.id,
  });

  // Get first enrolled class's subjectId for gap-map query
  const primarySubjectId =
    studentInfoQuery.data?.enrolledClasses?.[0]?.subjectId;

  const gapMapQuery = useQuery({
    queryKey: QUERY_KEYS.gapMap(user?.id || ""),
    queryFn: () => {
      if (!user?.id) throw new Error("User ID not available");
      if (!primarySubjectId) throw new Error("Subject ID not available");
      return fetchGapMap(user.id, primarySubjectId);
    },
    // Only fetch gap-map if student is enrolled and has a subject
    enabled: !!user?.id && !!primarySubjectId,
  });

  const studyPlansQuery = useQuery({
    queryKey: ["student", "study-plans", user?.id] as const,
    queryFn: () => {
      if (!user?.id) throw new Error("User ID not available");
      return fetchStudyPlans(user.id);
    },
    // Only fetch study plans if student is enrolled
    enabled: !!user?.id && studentInfoQuery.data?.isEnrolled === true,
  });

  const assessmentsQuery = useQuery({
    queryKey: [
      "student",
      "assessments",
      user?.id,
      studentInfoQuery.data?.classId,
    ] as const,
    queryFn: () => {
      const classId = studentInfoQuery.data?.classId;
      if (!classId) throw new Error("Class ID not available");
      return fetchAssessments(classId);
    },
    enabled: !!user?.id && !!studentInfoQuery.data?.classId,
  });

  const isLoading =
    gapMapQuery.isLoading ||
    studyPlansQuery.isLoading ||
    assessmentsQuery.isLoading ||
    studentInfoQuery.isLoading;

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
    isLoading,
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
