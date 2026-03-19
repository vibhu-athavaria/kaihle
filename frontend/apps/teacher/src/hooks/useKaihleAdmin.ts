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
  status: "ACTIVE" | "TRIAL" | "SUSPENDED";
  created_at: string;
  trial_expires_at: string | null;
  trial_end_date: string | null;
  subscription_status: string;
  teacher_count: number;
  student_count: number;
  parent_count: number;
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
  message?: string;
}

export interface SchoolAnalytics {
  teacher_count: number;
  student_count: number;
  parent_count: number;
  onboarding_percentage: number;
  onboarded_students: number;
  total_students: number;
}

export interface SchoolsResponse {
  schools: School[];
}

export function usePlatformStats() {
  return useQuery({
    queryKey: ["platform", "stats"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/admin/platform/stats");
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
      const response = await apiClient.get("/api/v1/admin/schools", { params });
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
      const response = await apiClient.get(`/api/v1/admin/schools/${schoolId}`);
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
    }) => {
      const response = await apiClient.post("/api/v1/admin/schools", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
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
        `/api/v1/admin/schools/${payload.id}/extend-trial`,
        payload.data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
    },
  });
}
