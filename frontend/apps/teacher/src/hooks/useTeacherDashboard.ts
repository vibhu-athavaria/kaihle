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

const QUERY_KEYS = {
  classes: (schoolId: string) => ["teacher", "classes", schoolId] as const,
  dashboard: (schoolId: string) => ["teacher", "dashboard", schoolId] as const,
};

async function fetchTeacherClasses(schoolId: string): Promise<TeacherClass[]> {
  const response = await apiClient.get(
    `/api/v1/schools/${schoolId}/classes?teacher_id=me`,
  );
  return response.data;
}

async function fetchClassAnalytics(
  schoolId: string,
): Promise<Record<string, number>> {
  const response = await apiClient.get(`/api/v1/schools/${schoolId}/analytics`);
  return response.data;
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
  const classesQuery = useQuery({
    queryKey: QUERY_KEYS.classes(schoolId || ""),
    queryFn: () => fetchTeacherClasses(schoolId!),
    enabled: !!schoolId,
  });

  const analyticsQuery = useQuery({
    queryKey: QUERY_KEYS.dashboard(schoolId || ""),
    queryFn: () => fetchClassAnalytics(schoolId!),
    enabled: !!schoolId,
  });

  const lessonPlanQueries = useQuery({
    queryKey: ["teacher", "lesson-plans", schoolId],
    queryFn: async () => {
      if (!classesQuery.data) return null;
      const classesWithPlans = classesQuery.data.filter(
        (c) => c.lessonPlanStatus === "ready",
      );
      if (classesWithPlans.length === 0) return null;

      const results = await Promise.all(
        classesWithPlans.map((c) => fetchLessonPlan(c.id)),
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
    enabled: !!classesQuery.data,
  });

  const isLoading =
    classesQuery.isLoading ||
    analyticsQuery.isLoading ||
    lessonPlanQueries.isLoading;

  const pendingActions: PendingAction[] = [];

  if (classesQuery.data) {
    for (const cls of classesQuery.data) {
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
      classes: classesQuery.data || [],
      pendingActions,
      lessonPlan: lessonPlanQueries.data || null,
    } as TeacherDashboardData,
    isLoading,
    isError: classesQuery.isError || analyticsQuery.isError,
  };
}
