import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface School {
  id: string;
  name: string;
  slug: string;
  country: string | null;
  city: string | null;
  timezone: string;
  plan_tier: "TRIAL" | "STARTER" | "GROWTH" | "SCALE";
  subscription_status: "ACTIVE" | "TRIAL" | "SUSPENDED";
  trial_end_date: string | null;
  mrr: number | null;
  created_at: string;
}

export interface SchoolAnalytics {
  teachers_count: number;
  students_count: number;
  assessments_completed: number;
  avg_mastery: number;
}

export interface PlatformStats {
  total_schools: number;
  total_students: number;
  mrr: number;
  uptime: number;
  latency_ms: number;
}

export interface RecentActivity {
  id: string;
  type: "SCHOOL_ENROLLED" | "TRIAL_EXTENDED" | "PAYMENT_RECEIVED";
  message: string;
  timestamp: string;
}

export interface CreateSchoolPayload {
  name: string;
  slug: string;
  country?: string;
  city?: string;
  timezone: string;
  plan_tier: "TRIAL" | "STARTER" | "GROWTH" | "SCALE";
  admin_email: string;
  admin_first_name: string;
  admin_last_name: string;
}

export interface ExtendTrialPayload {
  days: 7 | 14 | 30;
  reason: string;
}

export interface UpdateSchoolPayload {
  subscription_status?: "ACTIVE" | "TRIAL" | "SUSPENDED";
  plan_tier?: "TRIAL" | "STARTER" | "GROWTH" | "SCALE";
}

function getAdminSchools(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size)
    searchParams.set("page_size", String(params.page_size));
  if (params?.status) searchParams.set("status", params.status);
  const query = searchParams.toString();
  return apiClient.get<{ schools: School[]; total: number }>(
    `/api/v1/admin/schools${query ? `?${query}` : ""}`,
  );
}

function getAdminSchool(id: string) {
  return apiClient.get<School>(`/api/v1/admin/schools/${id}`);
}

function getSchoolAnalytics(schoolId: string) {
  return apiClient.get<SchoolAnalytics>(
    `/api/v1/schools/${schoolId}/analytics`,
  );
}

function getPlatformStats() {
  return apiClient.get<PlatformStats>("/api/v1/admin/stats");
}

function getRecentActivity() {
  return apiClient.get<RecentActivity[]>("/api/v1/admin/activity");
}

function createSchool(data: CreateSchoolPayload) {
  return apiClient.post<School>("/api/v1/admin/schools", data);
}

function updateSchool(id: string, data: UpdateSchoolPayload) {
  return apiClient.patch<School>(`/api/v1/admin/schools/${id}`, data);
}

function extendTrial(id: string, data: ExtendTrialPayload) {
  return apiClient.post<{ trial_end_date: string }>(
    `/api/v1/admin/schools/${id}/trial-extension`,
    data,
  );
}

export function useAdminSchools(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: ["admin", "schools", params],
    queryFn: () => getAdminSchools(params),
    select: (res) => res.data,
  });
}

export function useAdminSchool(id: string) {
  return useQuery({
    queryKey: ["admin", "school", id],
    queryFn: () => getAdminSchool(id),
    select: (res) => res.data,
    enabled: !!id,
  });
}

export function useSchoolAnalytics(schoolId: string) {
  return useQuery({
    queryKey: ["school", schoolId, "analytics"],
    queryFn: () => getSchoolAnalytics(schoolId),
    select: (res) => res.data,
    enabled: !!schoolId,
  });
}

export function usePlatformStats() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: getPlatformStats,
    select: (res) => res.data,
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ["admin", "activity"],
    queryFn: getRecentActivity,
    select: (res) => res.data,
  });
}

export function useCreateSchool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSchool,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
  });
}

export function useUpdateSchool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateSchoolPayload }) =>
      updateSchool(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "school", id] });
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
    },
  });
}

export function useExtendTrial() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ExtendTrialPayload }) =>
      extendTrial(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "school", id] });
      queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "activity"] });
    },
  });
}
