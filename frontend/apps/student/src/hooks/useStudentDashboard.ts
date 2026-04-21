import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useStudentInfo } from "./useStudentInfo";
import { useStudentAssessments } from "./useStudentAssessments";

interface StudyPlan {
  id: string;
  title: string;
  status: "ACTIVE" | "IN_PROGRESS" | "COMPLETED";
}

interface StudyPlansResponse {
  data: StudyPlan[];
}

export interface DashboardData {
  studyPlans: StudyPlan[];
  activeAssessmentCount: number;
}

interface UseStudentDashboardResult {
  data: DashboardData | undefined;
  isPending: boolean;
  isError: boolean;
  errMessage: string | undefined;
  refetch: () => Promise<void>;
}

export function useStudentDashboard(): UseStudentDashboardResult {
  const studentInfoQuery = useStudentInfo();

  const classIds = (studentInfoQuery.data?.enrolledClasses ?? []).map(
    (c) => c.classId,
  );

  const studyPlansQuery = useQuery({
    queryKey: ["student", "study-plans"] as const,
    queryFn: async (): Promise<StudyPlan[]> => {
      const res = await apiClient.get<StudyPlansResponse>(
        `/api/v1/students/me/study-plans?status=active,in_progress&limit=10`,
      );
      return res.data.data;
    },
    enabled: studentInfoQuery.data?.isEnrolled === true,
  });

  const {
    teacherAssessments,
    isPending: assessmentsPending,
    isError: assessmentsError,
  } = useStudentAssessments(classIds, studentInfoQuery.data?.id);

  const isPending =
    studentInfoQuery.isPending ||
    studyPlansQuery.isPending ||
    assessmentsPending;

  const isError =
    studentInfoQuery.isError || studyPlansQuery.isError || assessmentsError;

  const errMessage =
    studentInfoQuery.error?.message ?? studyPlansQuery.error?.message;

  const data = studentInfoQuery.data
    ? {
        studyPlans: studyPlansQuery.data ?? [],
        activeAssessmentCount: teacherAssessments.filter(
          (a) => a.status === "ACTIVE",
        ).length,
      }
    : undefined;

  return {
    data,
    isPending,
    isError,
    errMessage,
    refetch: async () => {
      await Promise.all([
        studentInfoQuery.refetch(),
        studyPlansQuery.refetch(),
      ]);
    },
  };
}
