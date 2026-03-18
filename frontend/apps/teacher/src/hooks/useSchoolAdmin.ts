import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: "TEACHER" | "STUDENT" | "PARENT";
  status: "ACTIVE" | "INVITED" | "INACTIVE";
  avatar_url?: string;
  created_at: string;
}

export interface Class {
  id: string;
  name: string;
  subject: string;
  grade: number;
  teacher_id: string;
  teacher_name: string;
  student_count: number;
  curriculum_id: string;
  curriculum_name: string;
  status: "ACTIVE" | "INACTIVE";
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
  level: string;
}

export interface Grade {
  id: string;
  level: number;
  label: string;
}

export interface InviteUserPayload {
  first_name: string;
  last_name: string;
  email: string;
  role: "TEACHER" | "STUDENT" | "PARENT";
}

export interface CreateClassPayload {
  name: string;
  subject: string;
  grade: number;
  curriculum_id: string;
  teacher_id?: string;
}

export interface EnrollStudentsPayload {
  student_ids: string[];
}

function getSchoolId(): string {
  const user = JSON.parse(localStorage.getItem("auth_user") || "{}");
  return user.school_id || "default";
}

export function useSchoolAnalytics() {
  const schoolId = getSchoolId();
  return useQuery({
    queryKey: ["school-analytics", schoolId],
    queryFn: async () => {
      const { data } = await apiClient.get<SchoolAnalytics>(
        `/api/v1/schools/${schoolId}/analytics`,
      );
      return data;
    },
  });
}

export function useSchoolUsers(role: "TEACHER" | "STUDENT" | "PARENT") {
  const schoolId = getSchoolId();
  return useQuery({
    queryKey: ["school-users", schoolId, role],
    queryFn: async () => {
      const { data } = await apiClient.get<User[]>(
        `/api/v1/schools/${schoolId}/users`,
        { params: { role } },
      );
      return data;
    },
  });
}

export function useSchoolClasses() {
  const schoolId = getSchoolId();
  return useQuery({
    queryKey: ["school-classes", schoolId],
    queryFn: async () => {
      const { data } = await apiClient.get<Class[]>(
        `/api/v1/schools/${schoolId}/classes`,
      );
      return data;
    },
  });
}

export function useCurricula() {
  return useQuery({
    queryKey: ["curricula"],
    queryFn: async () => {
      const { data } = await apiClient.get<Curriculum[]>("/api/v1/curricula");
      return data;
    },
  });
}

export function useGrades() {
  return useQuery({
    queryKey: ["grades"],
    queryFn: async () => {
      const { data } = await apiClient.get<Grade[]>("/api/v1/grades");
      return data;
    },
  });
}

export function useInviteUser() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async (payload: InviteUserPayload) => {
      const { data } = await apiClient.post<User>(
        `/api/v1/schools/${schoolId}/users`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-users", schoolId] });
    },
  });
}

export function useCreateClass() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async (payload: CreateClassPayload) => {
      const { data } = await apiClient.post<Class>(
        `/api/v1/schools/${schoolId}/classes`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-classes", schoolId] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async ({
      userId,
      ...payload
    }: {
      userId: string;
      status?: string;
    }) => {
      const { data } = await apiClient.patch<User>(
        `/api/v1/schools/${schoolId}/users/${userId}`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-users", schoolId] });
    },
  });
}

export function useEnrollStudents(classId: string) {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async (payload: EnrollStudentsPayload) => {
      const { data } = await apiClient.post(
        `/api/v1/classes/${classId}/enroll`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-classes", schoolId] });
    },
  });
}

export function useUpdateClass() {
  const queryClient = useQueryClient();
  const schoolId = getSchoolId();

  return useMutation({
    mutationFn: async ({
      classId,
      ...payload
    }: {
      classId: string;
      teacher_id?: string;
      status?: string;
    }) => {
      const { data } = await apiClient.patch<Class>(
        `/api/v1/schools/${schoolId}/classes/${classId}`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-classes", schoolId] });
    },
  });
}
