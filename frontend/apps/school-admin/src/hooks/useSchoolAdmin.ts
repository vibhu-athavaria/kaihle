import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuthStore } from "@kaihle/auth";
import { UserRole, type UserRole as UserRoleType } from "@kaihle/types";

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

export interface SchoolAnalytics {
  teacher_count: number;
  student_count: number;
  parent_count: number;
  onboarding_percentage: number;
  onboarded_students: number;
  total_students: number;
}

export interface Curriculum {
  id: string;
  name: string;
}

export interface Grade {
  id: string;
  level: number;
}

function getSchoolId(): string {
  const user = useAuthStore.getState().user;
  if (!user?.school_id) {
    throw new Error("No school_id found for current user");
  }
  return user.school_id;
}

export function useSchoolAnalytics() {
  return useQuery({
    queryKey: ["school", "analytics"],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const response = await apiClient.get(
        `/api/v1/schools/${schoolId}/analytics`,
      );
      return response.data as SchoolAnalytics;
    },
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useSchoolClasses() {
  return useQuery({
    queryKey: ["school", "classes"],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const response = await apiClient.get(
        `/api/v1/schools/${schoolId}/classes`,
      );
      return response.data as Class[];
    },
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useSchoolUsers(
  role:
    | typeof UserRole.TEACHER
    | typeof UserRole.STUDENT
    | typeof UserRole.PARENT,
) {
  return useQuery({
    queryKey: ["school", "users", role],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const response = await apiClient.get(
        `/api/v1/schools/${schoolId}/users?role=${role}`,
      );
      // Handle both paginated response (object with users array) and direct array
      const rawUsers = response.data?.users ?? response.data;

      // Map backend fields to frontend interface
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
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useCurricula() {
  return useQuery({
    queryKey: ["curricula"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/curricula");
      return response.data as Curriculum[];
    },
  });
}

export function useGrades() {
  return useQuery({
    queryKey: ["grades"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/grades");
      return response.data as Grade[];
    },
  });
}

export function useInviteUser() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async (data: {
      first_name: string;
      last_name: string;
      email: string;
      role:
        | typeof UserRole.TEACHER
        | typeof UserRole.STUDENT
        | typeof UserRole.PARENT;
    }) => {
      const response = await apiClient.post(
        `/api/v1/schools/${schoolId}/users`,
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school", "users"] });
    },
  });
}

export function useCreateClass() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async (data: {
      name: string;
      subject: string;
      grade: number;
      curriculum_id: string;
      teacher_id?: string;
    }) => {
      const response = await apiClient.post(
        `/api/v1/schools/${schoolId}/classes`,
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] });
    },
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
      const response = await apiClient.patch(
        `/api/v1/classes/${data.classId}`,
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async (data: {
      userId: string;
      status: "ACTIVE" | "INACTIVE";
    }) => {
      const response = await apiClient.patch(
        `/api/v1/schools/${schoolId}/users/${data.userId}`,
        { status: data.status },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school", "users"] });
    },
  });
}

export function useEnrollStudents(classId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { student_ids: string[] }) => {
      const response = await apiClient.post(
        `/api/v1/classes/${classId}/enroll`,
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school", "classes"] });
    },
  });
}
