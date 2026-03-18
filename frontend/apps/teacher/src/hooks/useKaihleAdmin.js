import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
export function usePlatformStats() {
    return useQuery({
        queryKey: ["platform", "stats"],
        queryFn: async () => {
            const response = await apiClient.get("/api/v1/admin/platform/stats");
            return response.data;
        },
    });
}
export function useAdminSchools(params) {
    return useQuery({
        queryKey: ["admin", "schools", params],
        queryFn: async () => {
            const response = await apiClient.get("/api/v1/admin/schools", { params });
            return response.data;
        },
    });
}
export function useRecentActivity() {
    return useQuery({
        queryKey: ["admin", "activity"],
        queryFn: async () => {
            const response = await apiClient.get("/api/v1/admin/recent-activity");
            return response.data;
        },
    });
}
export function useAdminSchool(schoolId) {
    return useQuery({
        queryKey: ["admin", "school", schoolId],
        queryFn: async () => {
            const response = await apiClient.get(`/api/v1/admin/schools/${schoolId}`);
            return response.data;
        },
        enabled: !!schoolId,
    });
}
export function useSchoolAnalytics(schoolId) {
    return useQuery({
        queryKey: ["admin", "school", schoolId, "analytics"],
        queryFn: async () => {
            const response = await apiClient.get(`/api/v1/admin/schools/${schoolId}/analytics`);
            return response.data;
        },
        enabled: !!schoolId,
    });
}
export function useCreateSchool() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data) => {
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
        mutationFn: async (payload) => {
            const response = await apiClient.post(`/api/v1/admin/schools/${payload.id}/extend-trial`, payload.data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin", "schools"] });
        },
    });
}
