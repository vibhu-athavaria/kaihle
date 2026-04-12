import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { PendingAction } from "../pages/dashboard/PendingActionBanner";

export interface TeacherClass {
  id: string;
  name: string;
  subjectId: string;
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

async function fetchTeacherDashboard(schoolId: string): Promise<
  TeacherClass[]
> {
  const [classesRes, analyticsRes] = await Promise.all([
    apiClient.get(`/api/v1/schools/${schoolId}/classes`),
    apiClient
      .get(`/api/v1/schools/${schoolId}/analytics`)
      .catch(() => ({ data: {} })),
  ]);

  // Build a lookup map from analytics class breakdowns
  const analyticsMap = new Map<
    string,
    { studentCount: number; avgMastery: number | null }
  >();
  const classBreakdowns = analyticsRes.data?.classes || [];
  for (const cb of classBreakdowns) {
    analyticsMap.set(cb.class_id, {
      studentCount: cb.student_count ?? 0,
      avgMastery: cb.avg_mastery ?? null,
    });
  }

  // Transform classes to include subjectName, gradeName, and analytics data
  const classes = (classesRes.data || []).map((c: any) => {
    const analytics = analyticsMap.get(c.id);
    return {
      id: c.id,
      name: c.name,
      subjectId: c.subject_id ?? "",
      subjectName: c.subjectName || c.name?.split(" ")[0] || "Unknown",
      gradeName: c.gradeName || c.name?.split(" ")[1] || "Unknown",
      studentCount: analytics?.studentCount ?? 0,
      avgMastery: analytics?.avgMastery ?? null,
      lessonPlanStatus: "none" as const,
    };
  });

  return classes;
}

export function useTeacherDashboard(schoolId: string | null) {
  const dashboardQuery = useQuery({
    queryKey: ["teacher", "dashboard", schoolId],
    queryFn: () => fetchTeacherDashboard(schoolId!),
    enabled: !!schoolId,
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
      lessonPlan: null,
    } as TeacherDashboardData,
    isLoading: dashboardQuery.isLoading,
    isError: dashboardQuery.isError,
    user: null, // Will be filled from auth store
  };
}
