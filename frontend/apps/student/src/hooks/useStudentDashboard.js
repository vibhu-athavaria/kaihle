import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";
const QUERY_KEYS = {
    dashboard: (studentId) => ["student", "dashboard", studentId],
    gapMap: (studentId) => ["student", "gap-map", studentId],
};
async function fetchGapMap(studentId) {
    const response = await apiClient.get(`/api/v1/students/${studentId}/gap-map`);
    return response.data;
}
async function fetchStudyPlans(studentId) {
    const response = await apiClient.get(`/api/v1/students/${studentId}/study-plans?status=active,in_progress&limit=10`);
    return response.data.data;
}
async function fetchAssessments(classId) {
    const response = await apiClient.get(`/api/v1/classes/${classId}/assessments?status=ACTIVE&limit=5`);
    return response.data;
}
async function fetchStudentInfo(studentId) {
    const response = await apiClient.get(`/api/v1/students/${studentId}/info`);
    return response.data;
}
export function useStudentDashboard() {
    const { user } = useAuth();
    const gapMapQuery = useQuery({
        queryKey: QUERY_KEYS.gapMap(user?.id || ""),
        queryFn: () => fetchGapMap(user.id),
        enabled: !!user?.id,
    });
    const studyPlansQuery = useQuery({
        queryKey: ["student", "study-plans", user?.id],
        queryFn: () => fetchStudyPlans(user.id),
        enabled: !!user?.id,
    });
    const assessmentsQuery = useQuery({
        queryKey: ["student", "assessments", user?.id],
        queryFn: () => fetchAssessments("default"),
        enabled: !!user?.id,
    });
    const studentInfoQuery = useQuery({
        queryKey: ["student", "info", user?.id],
        queryFn: () => fetchStudentInfo(user.id),
        enabled: !!user?.id,
    });
    const isLoading = gapMapQuery.isLoading ||
        studyPlansQuery.isLoading ||
        assessmentsQuery.isLoading ||
        studentInfoQuery.isLoading;
    const isError = gapMapQuery.isError ||
        studyPlansQuery.isError ||
        assessmentsQuery.isError ||
        studentInfoQuery.isError;
    const data = gapMapQuery.data && studyPlansQuery.data && studentInfoQuery.data
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
