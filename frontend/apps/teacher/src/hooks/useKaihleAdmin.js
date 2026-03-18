import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
function getAdminSchools(params) {
    const searchParams = new URLSearchParams();
    if (params?.page)
        searchParams.set("page", String(params.page));
    if (params?.page_size)
        searchParams.set("page_size", String(params.page_size));
    if (params?.status)
        searchParams.set("status", params.status);
    const query = searchParams.toString();
    return apiClient.get(`/api/v1/admin/schools${query ? `?${query}` : ""}`);
}
function getAdminSchool(id) {
    return apiClient.get(`/api/v1/admin/schools/${id}`);
}
function getSchoolAnalytics(schoolId) {
    return apiClient.get(`/api/v1/schools/${schoolId}/analytics`);
}
function getPlatformStats() {
    return apiClient.get("/api/v1/admin/stats");
}
function getRecentActivity() {
    return apiClient.get("/api/v1/admin/activity");
}
function createSchool(data) {
    return apiClient.post("/api/v1/admin/schools", data);
}
function updateSchool(id, data) {
    return apiClient.patch(`/api/v1/admin/schools/${id}`, data);
}
function extendTrial(id, data) {
    return apiClient.post(`/api/v1/admin/schools/${id}/trial-extension`, data);
}
export function useAdminSchools(params) {
    return useQuery({
        queryKey: ["admin", "schools", params],
        queryFn: () => getAdminSchools(params),
        select: (res) => res.data,
    });
}
export function useAdminSchool(id) {
    return useQuery({
        queryKey: ["admin", "school", id],
        queryFn: () => getAdminSchool(id),
        select: (res) => res.data,
        enabled: !!id,
    });
}
export function useSchoolAnalytics(schoolId) {
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
        mutationFn: ({ id, data }) => updateSchool(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: ["admin", "school", id] });
            queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
        },
    });
}
export function useExtendTrial() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ id, data }) => extendTrial(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: ["admin", "school", id] });
            queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
            queryClient.invalidateQueries({ queryKey: ["admin", "activity"] });
        },
    });
}
