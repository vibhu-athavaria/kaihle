import { useQuery, useQueries } from "@tanstack/react-query";
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
  studentsBelow: number;
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

interface ClassResponse {
  id: string;
  name: string;
  subject_id: string;
  grade_id: string;
}

interface ClassSummary {
  class_id: string;
  avg_mastery: number | null;
  student_count: number;
  students_below_threshold?: number;
}

interface GradeResponse {
  id: string;
  name: string;
}

interface SubjectResponse {
  id: string;
  name: string;
}

// Static seed data — cache forever
export function useGrades() {
  return useQuery<GradeResponse[]>({
    queryKey: ["grades"],
    queryFn: () =>
      apiClient
        .get("/api/v1/grades")
        .then((r) => r.data?.grades ?? r.data ?? []),
    staleTime: Infinity,
  });
}

export function useSubjects() {
  return useQuery<SubjectResponse[]>({
    queryKey: ["subjects"],
    queryFn: () =>
      apiClient
        .get("/api/v1/subjects")
        .then((r) => r.data?.subjects ?? r.data ?? []),
    staleTime: Infinity,
  });
}

export function useTeacherDashboard(schoolId: string | null) {
  const gradesQuery = useGrades();
  const subjectsQuery = useSubjects();

  const classesQuery = useQuery<ClassResponse[]>({
    queryKey: ["teacher", "classes", schoolId],
    queryFn: () =>
      apiClient
        .get(`/api/v1/schools/${schoolId}/classes`)
        .then((r) => r.data ?? []),
    enabled: !!schoolId,
    staleTime: 5 * 60 * 1000,
  });

  const classes: ClassResponse[] = classesQuery.data ?? [];

  // Build lookup maps from static seed data
  const gradeMap: Record<string, string> = {};
  for (const g of gradesQuery.data ?? []) {
    gradeMap[g.id] = g.name;
  }
  const subjectMap: Record<string, string> = {};
  for (const s of subjectsQuery.data ?? []) {
    subjectMap[s.id] = s.name;
  }

  // Parallel summary calls — one per class
  const summaryQueries = useQueries({
    queries: classes.map((c) => ({
      queryKey: ["teacher", "class-summary", c.id],
      queryFn: () =>
        apiClient
          .get(`/api/v1/classes/${c.id}/summary`)
          .then((r) => r.data as ClassSummary)
          .catch(() => null),
      staleTime: 5 * 60 * 1000,
      enabled: !!c.id,
    })),
  });

  const enrichedClasses: TeacherClass[] = classes.map((c, i) => {
    const summary = summaryQueries[i]?.data;
    const gradeName = gradeMap[c.grade_id] ?? "";
    const subjectName = subjectMap[c.subject_id] ?? "";
    return {
      id: c.id,
      name: c.name,
      subjectId: c.subject_id,
      subjectName,
      gradeName,
      studentCount: summary?.student_count ?? 0,
      avgMastery: summary?.avg_mastery ?? null,
      studentsBelow: summary?.students_below_threshold ?? 0,
      lessonPlanStatus: "none" as const,
    };
  });

  const pendingActions: PendingAction[] = [];
  for (const cls of enrichedClasses) {
    if (cls.avgMastery === null) {
      pendingActions.push({
        type: "no-assessments",
        classId: cls.id,
        className: cls.name,
      });
    }
  }

  const isPending =
    classesQuery.isPending ||
    gradesQuery.isPending ||
    subjectsQuery.isPending ||
    summaryQueries.some((q) => q.isPending);

  return {
    data: {
      classes: enrichedClasses,
      pendingActions,
      lessonPlan: null,
    } as TeacherDashboardData,
    isLoading: isPending,
    isError: classesQuery.isError,
  };
}
