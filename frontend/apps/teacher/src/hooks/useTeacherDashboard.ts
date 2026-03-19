import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { PendingAction } from "../pages/dashboard/PendingActionBanner";

export interface TeacherClass {
  id: string;
  name: string;
  subjectName: string;
  gradeName: string;
  studentCount: number;
  avgMastery: number | null;
  lessonPlanStatus: "ready" | "generating" | "none";
}

export interface LessonPlanInfo {
  classId: string;
  className: string;
  topics: string[];
}

export interface TeacherDashboardData {
  classes: TeacherClass[];
  pendingActions: PendingAction[];
  lessonPlan: LessonPlanInfo | null;
}

async function fetchTeacherDashboard(schoolId: string): Promise<{
  classes: TeacherClass[];
  analytics: Record<string, number>;
}> {
  const [classesRes, analyticsRes] = await Promise.all([
    apiClient.get(`/api/v1/schools/${schoolId}/classes`),
    apiClient
      .get(`/api/v1/schools/${schoolId}/analytics`)
      .catch(() => ({ data: {} })),
  ]);
  return {
    classes: classesRes.data,
    analytics: analyticsRes.data,
  };
}

async function fetchLessonPlan(
  classId: string,
): Promise<{ topics: string[] } | null> {
  const response = await apiClient.get(
    `/api/v1/classes/${classId}/lesson-plans?limit=1`,
  );
  return response.data.length > 0 ? response.data[0] : null;
}

export function useTeacherDashboard(schoolId: string | null) {
  const dashboardQuery = useQuery({
    queryKey: ["teacher", "dashboard", schoolId],
    queryFn: () => fetchTeacherDashboard(schoolId!),
    enabled: !!schoolId,
  });

  const lessonPlanQuery = useQuery({
    queryKey: ["teacher", "lesson-plans", schoolId],
    queryFn: async () => {
      if (!dashboardQuery.data) return null;
      const classesWithPlans = dashboardQuery.data.classes.filter(
        (c: TeacherClass) => c.lessonPlanStatus === "ready",
      );
      if (classesWithPlans.length === 0) return null;

      const results = await Promise.all(
        classesWithPlans.map((c: TeacherClass) => fetchLessonPlan(c.id)),
      );
      const firstPlan = results.find((r) => r !== null);
      if (!firstPlan) return null;

      const classInfo = classesWithPlans.find((_, i) => results[i] !== null);
      return classInfo
        ? {
            classId: classInfo.id,
            className: classInfo.name,
            topics: firstPlan.topics,
          }
        : null;
    },
    enabled: !!dashboardQuery.data,
  });

  const pendingActions: PendingAction[] = [];

  if (dashboardQuery.data) {
    for (const cls of dashboardQuery.data.classes) {
      if (cls.avgMastery !== null && cls.avgMastery < 0.4) {
        pendingActions.push({
          type: "study-plan",
          classId: cls.id,
          className: cls.name,
          studentCount: Math.ceil(cls.studentCount * 0.3),
        });
      }
      if (cls.avgMastery === null) {
        pendingActions.push({
          type: "no-assessments",
          classId: cls.id,
          className: cls.name,
        });
      }
    }
  }

  return {
    data: {
      classes: dashboardQuery.data?.classes || [],
      pendingActions,
      lessonPlan: lessonPlanQuery.data || null,
    } as TeacherDashboardData,
    isLoading: dashboardQuery.isLoading || lessonPlanQuery.isLoading,
    isError: dashboardQuery.isError,
  };
}
