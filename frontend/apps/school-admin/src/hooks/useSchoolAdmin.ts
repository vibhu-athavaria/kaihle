// frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";
import { UserRole, type UserRole as UserRoleType } from "@kaihle/types";

// ── types ────────────────────────────────────────────────────────────────────

// Legacy types kept for backward compatibility with existing pages
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRoleType;
  status: "ACTIVE" | "INVITED" | "INACTIVE";
}

export interface Class {
  id: string;
  name: string;
  subject: string;
  grade: number;
  teacher_id: string | null;
  teacher_name: string | null;
  student_count: number;
  is_active: boolean;
}

export interface OnboardingFunnel {
  invited: number;
  password_set: number;
  profile_complete: number;
  diagnostic_done: number;
}

export interface ClassBreakdown {
  class_id: string;
  class_name: string;
  subject_name?: string;
  teacher_name?: string;
  student_count: number;
  avg_mastery: number | null;
  assessments_completed: number;
}

export interface AtRiskStudent {
  student_id: string;
  first_name: string;
  last_name: string;
  worst_mastery: number | null;
  needs_work_class_count: number;
}

export interface SchoolAnalytics {
  school_id: string;
  generated_at: string;
  total_students: number;
  total_teachers?: number;
  active_students: number;
  assessments_completed: number;
  study_plans_active: number;
  onboarding_funnel: OnboardingFunnel;
  classes: ClassBreakdown[];
  at_risk_students: AtRiskStudent[];
}

export interface ClassSummary {
  id: string;
  name: string;
  subject_name: string;
  grade_level: number;
  teacher_id: string | null;
  teacher_name: string | null;
  student_count: number;
  avg_mastery: number | null;
  students_below_threshold: number;
  has_teacher: boolean;
  diagnostic_status: "setup_needed" | "pending" | "has_data";
}

export interface StudentListItem {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  last_login_at: string | null;
  worst_mastery: number | null;
  class_count: number;
  needs_work_class_count: number;
  diagnostic_completed: boolean;
}

export interface Curriculum {
  id: string;
  name: string;
}
export interface Grade {
  id: string;
  level: number;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
}

export interface AssessmentAttempt {
  id: string;
  assessment_name: string;
  class_name?: string;
  completed_at: string | null;
  score: number | null;
  assessment_type: string;
}

export interface StudyPlan {
  id: string;
  title: string;
  assigned_at: string;
  resources_completed: number;
  total_resources: number;
  status: string;
  is_active?: boolean;
}

// ── queries ──────────────────────────────────────────────────────────────────

export function useSchoolAnalytics(fromDate?: string, toDate?: string) {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  return useQuery({
    queryKey: ["school", "analytics", schoolId, fromDate, toDate],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (fromDate) params.set("from_date", fromDate);
      if (toDate) params.set("to_date", toDate);
      const qs = params.toString() ? `?${params}` : "";
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/analytics${qs}`,
      );
      return res.data as SchoolAnalytics;
    },
    enabled: !!schoolId,
  });
}

export function useSchoolClasses() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  return useQuery({
    queryKey: ["school", "classes", schoolId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/classes?include_summary=true`,
      );
      const raw: ClassSummary[] = res.data;
      return raw.map((c) => ({
        ...c,
        diagnostic_status: !c.has_teacher
          ? ("setup_needed" as const)
          : c.avg_mastery === null
            ? ("pending" as const)
            : ("has_data" as const),
      }));
    },
    enabled: !!schoolId,
  });
}

export function useSchoolStudents() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  return useQuery({
    queryKey: ["school", "users", "STUDENT", schoolId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/users?role=STUDENT`,
      );
      const raw = res.data?.users ?? res.data;
      return raw as StudentListItem[];
    },
    enabled: !!schoolId,
  });
}

export function useSchoolUsers(
  role:
    | typeof UserRole.TEACHER
    | typeof UserRole.STUDENT
    | typeof UserRole.PARENT,
) {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  return useQuery({
    queryKey: ["school", "users", role, schoolId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/users?role=${role}`,
      );
      const rawUsers = res.data?.users ?? res.data;

      const users: User[] = (rawUsers || []).map(
        (user: {
          id: string;
          email: string;
          first_name: string;
          last_name: string;
          role: string;
          is_active: boolean;
        }) => ({
          id: user.id,
          email: user.email,
          first_name: user.first_name,
          last_name: user.last_name,
          role: user.role,
          status: user.is_active ? ("ACTIVE" as const) : ("INACTIVE" as const),
        }),
      );

      return users;
    },
    enabled: !!schoolId,
  });
}

// ── Teacher detail ────────────────────────────────────────────────────────────

export interface AssignedClass {
  class_id: string;
  class_name: string;
  subject_name: string;
  grade_level: number;
  student_count: number;
  avg_mastery: number | null;
}

export interface TeacherDetail {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  assigned_classes: AssignedClass[];
}

export function useTeacherDetail(teacherId: string) {
  return useQuery({
    queryKey: ["teacher", teacherId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/teachers/${teacherId}`);
      return res.data as TeacherDetail;
    },
    enabled: !!teacherId,
  });
}

// ── Parent detail ─────────────────────────────────────────────────────────────

export interface LinkedStudent {
  student_id: string;
  first_name: string;
  last_name: string;
  worst_mastery: number | null;
  class_count: number;
}

export interface ParentDetail {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  linked_students: LinkedStudent[];
}

export function useParentDetail(parentId: string) {
  return useQuery({
    queryKey: ["parent", parentId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/parents/${parentId}`);
      return res.data as ParentDetail;
    },
    enabled: !!parentId,
  });
}

export function useStudentDetail(studentId: string) {
  return useQuery({
    queryKey: ["student", studentId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}`);
      return res.data;
    },
    enabled: !!studentId,
  });
}

export function useStudentAttempts(studentId: string | undefined) {
  return useQuery<AssessmentAttempt[]>({
    queryKey: ["student", studentId, "attempts"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}/attempts`);
      return (res.data?.data ?? res.data) as AssessmentAttempt[];
    },
    enabled: !!studentId,
  });
}

export function useStudentStudyPlans(studentId: string | undefined) {
  return useQuery<StudyPlan[]>({
    queryKey: ["student", studentId, "study-plans"],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/students/${studentId}/study-plans`,
      );
      return res.data as StudyPlan[];
    },
    enabled: !!studentId,
  });
}

export function useCurricula() {
  return useQuery({
    queryKey: ["curricula"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/curricula");
      return res.data as Curriculum[];
    },
    staleTime: Infinity,
  });
}

export function useGrades() {
  return useQuery({
    queryKey: ["grades"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/grades");
      return res.data as Grade[];
    },
    staleTime: Infinity,
  });
}

export function useSubjects(curriculumId?: string) {
  return useQuery({
    queryKey: ["subjects", curriculumId ?? "all"],
    queryFn: async () => {
      const url = curriculumId
        ? `/api/v1/subjects?curriculum_id=${curriculumId}`
        : "/api/v1/subjects";
      const res = await apiClient.get(url);
      return res.data as Subject[];
    },
    staleTime: Infinity,
  });
}

// ── mutations ────────────────────────────────────────────────────────────────

export function useInviteUser() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      first_name: string;
      last_name: string;
      email: string;
      role: UserRoleType;
      student_ids?: string[];
    }) => {
      if (!schoolId) throw new Error("No school_id for current user");
      const res = await apiClient.post(
        `/api/v1/schools/${schoolId}/users`,
        data,
      );
      return res.data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "users"] }),
  });
}

export interface UserDirectCreatePayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  role: "STUDENT" | "TEACHER" | "PARENT";
  age?: number;
  grade_id?: string;
  class_ids?: string[];
  student_ids?: string[];
}

export function useCreateUser() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: UserDirectCreatePayload) => {
      if (!schoolId) throw new Error("No school_id for current user");
      const res = await apiClient.post(
        `/api/v1/schools/${schoolId}/users/create`,
        data,
      );
      return res.data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "users"] }),
  });
}

export function useCreateClass() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      grade_id: string;
      subject_id: string;
      curriculum_id: string;
      teacher_id: string;
      academic_year: string;
    }) => {
      if (!schoolId) throw new Error("No school_id for current user");
      const res = await apiClient.post(
        `/api/v1/schools/${schoolId}/classes`,
        data,
      );
      return res.data as { id: string; name: string; academic_year: string };
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}

export function useUpdateClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      classId: string;
      name?: string;
      teacher_id?: string;
    }) => {
      const res = await apiClient.patch(
        `/api/v1/classes/${data.classId}`,
        data,
      );
      return res.data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}

export function useUpdateUser() {
  const schoolId = useAuthStore((state) => state.user?.school_id);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      userId: string;
      status: "ACTIVE" | "INACTIVE";
    }) => {
      if (!schoolId) throw new Error("No school_id for current user");
      const res = await apiClient.patch(
        `/api/v1/schools/${schoolId}/users/${data.userId}`,
        { status: data.status },
      );
      return res.data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "users"] }),
  });
}

export function useEnrollStudents(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { student_ids: string[] }) => {
      const res = await apiClient.post(
        `/api/v1/classes/${classId}/enrollments`,
        data,
      );
      return res.data as {
        enrolled: number;
        skipped: number;
        errors: string[];
      };
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}
