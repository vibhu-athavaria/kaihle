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

interface StudentInfo {
  firstName: string;
  gradeName: string;
  curriculumName: string;
  classId?: string;
  streakDays?: number;
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
  dashboard: (studentId: string) => ["student", "dashboard", studentId] as const,
  gapMap: (studentId: string) => ["student", "gap-map", studentId] as const,
};

async function fetchGapMap(studentId: string): Promise<GapMap> {
  const response = await apiClient.get<GapMap>(`/api/v1/students/${studentId}/gap-map`);
  return response.data;
}

async function fetchStudyPlans(studentId: string): Promise<StudyPlan[]> {
  const response = await apiClient.get<StudyPlansResponse>(
    `/api/v1/students/${studentId}/study-plans?status=active,in_progress&limit=10`
  );
  return response.data.data;
}

async function fetchAssessments(classId: string): Promise<Assessment[]> {
  const response = await apiClient.get<Assessment[]>(
    `/api/v1/classes/${classId}/assessments?status=ACTIVE&limit=5`
  );
  return response.data;
}

async function fetchStudentInfo(studentId: string): Promise<StudentInfo> {
  const response = await apiClient.get<StudentInfo>(`/api/v1/students/${studentId}/info`);
  return response.data;
}

interface UseStudentDashboardResult {
  data: DashboardData | undefined;
  isLoading: boolean;
  isError: boolean;
  refetch: () => Promise<void>;
}

export function useStudentDashboard(): UseStudentDashboardResult {
  const { user } = useAuth();

  const studentInfoQuery = useQuery({
    queryKey: ["student", "info", user?.id] as const,
    queryFn: () => fetchStudentInfo(user!.id),
    enabled: !!user?.id,
  });

  const gapMapQuery = useQuery({
    queryKey: QUERY_KEYS.gapMap(user?.id || ""),
    queryFn: () => fetchGapMap(user!.id),
    enabled: !!user?.id,
  });

  const studyPlansQuery = useQuery({
    queryKey: ["student", "study-plans", user?.id] as const,
    queryFn: () => fetchStudyPlans(user!.id),
    enabled: !!user?.id,
  });

  const assessmentsQuery = useQuery({
    queryKey: ["student", "assessments", user?.id, studentInfoQuery.data?.classId] as const,
    queryFn: () => fetchAssessments(studentInfoQuery.data?.classId || ""),
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

  const data =
    gapMapQuery.data && studyPlansQuery.data && studentInfoQuery.data
      ? {
          gapMap: gapMapQuery.data,
          studyPlans: studyPlansQuery.data,
          assessments: assessmentsQuery.data || [],
          studentInfo: studentInfoQuery.data,
        }
      : undefined;

  return {
    data,
    isLoading,
    isError,
    refetch: async () => {
      await gapMapQuery.refetch();
      await studyPlansQuery.refetch();
      await assessmentsQuery.refetch();
      await studentInfoQuery.refetch();
    },
  };
}
