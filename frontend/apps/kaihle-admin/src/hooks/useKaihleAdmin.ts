import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface School {
  id: string;
  name: string;
  slug: string;
  country: string;
  city: string;
  timezone: string;
  plan_tier: string;
  subscription_status: "ACTIVE" | "TRIAL" | "SUSPENDED";
  joined: string;
  trial_expires_at: string | null;
  trial_end_date: string | null;
  teacher_count: number;
  student_count: number;
  parent_count: number;
  admin_user_id: string | null;
  admin_email: string | null;
}

export interface PlatformStats {
  total_schools: number;
  total_students: number;
  total_teachers: number;
  mrr: number;
  mrr_growth: number;
  uptime?: number;
  latency_ms?: number;
}

export interface RecentActivity {
  id: string;
  type: string;
  description: string;
  timestamp: string;
}

export interface SchoolAnalytics {
  teacher_count: number;
  student_count: number;
  parent_count: number;
  onboarding_percentage: number;
  onboarded_students: number;
  total_students: number;
  assessments_completed: number;
  avg_mastery: number;
}

export interface SchoolsResponse {
  schools: School[];
}

export function usePlatformStats() {
  return useQuery({
    queryKey: ["platform", "stats"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/platform/stats");
      return response.data as PlatformStats;
    },
  });
}

export function useAdminSchools(params?: {
  page_size?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: ["admin", "schools", params],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/schools", { params });
      return response.data as SchoolsResponse;
    },
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ["admin", "activity"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/admin/recent-activity");
      return response.data as RecentActivity[];
    },
  });
}

export function useAdminSchool(schoolId: string) {
  return useQuery({
    queryKey: ["admin", "school", schoolId],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/schools/${schoolId}`);
      return response.data as School;
    },
    enabled: !!schoolId,
  });
}

export function useSchoolAnalytics(schoolId: string) {
  return useQuery({
    queryKey: ["admin", "school", schoolId, "analytics"],
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/v1/admin/schools/${schoolId}/analytics`,
      );
      return response.data as SchoolAnalytics;
    },
    enabled: !!schoolId,
  });
}

export function useCreateSchool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      name: string;
      slug: string;
      country: string;
      city: string;
      timezone: string;
      plan_tier: string;
      admin_email: string;
      admin_first_name: string;
      admin_last_name: string;
      admin_password?: string;
    }) => {
      const response = await apiClient.post("/api/v1/schools", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
    },
  });
}

export function useUpdateSchool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      id: string;
      data: {
        name?: string;
        country?: string;
        city?: string;
        timezone?: string;
        is_active?: boolean;
      };
    }) => {
      const response = await apiClient.patch(
        `/api/v1/schools/${payload.id}`,
        payload.data,
      );
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["admin", "school", variables.id],
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
    },
  });
}

export function useUpdateSchoolAdminPassword() {
  return useMutation({
    mutationFn: async (payload: {
      schoolId: string;
      userId: string;
      password: string;
    }) => {
      const response = await apiClient.patch(
        `/api/v1/schools/${payload.schoolId}/users/${payload.userId}`,
        { password: payload.password },
      );
      return response.data;
    },
  });
}

export function useExtendTrial() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      id: string;
      data: { days: number; reason: string };
    }) => {
      const response = await apiClient.post(
        `/api/v1/schools/${payload.id}/extend-trial`,
        payload.data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
    },
  });
}
