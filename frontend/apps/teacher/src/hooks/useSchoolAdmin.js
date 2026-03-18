import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuthStore } from "@kaihle/auth";
function getSchoolId() {
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
            const response = await apiClient.get(`/api/v1/schools/${schoolId}/analytics`);
            return response.data;
        },
        enabled: !!useAuthStore.getState().user?.school_id,
    });
}
export function useSchoolClasses() {
    return useQuery({
        queryKey: ["school", "classes"],
        queryFn: async () => {
            const schoolId = getSchoolId();
            const response = await apiClient.get(`/api/v1/schools/${schoolId}/classes`);
            return response.data;
        },
        enabled: !!useAuthStore.getState().user?.school_id,
    });
}
export function useSchoolUsers(role) {
    return useQuery({
        queryKey: ["school", "users", role],
        queryFn: async () => {
            const schoolId = getSchoolId();
            const response = await apiClient.get(`/api/v1/schools/${schoolId}/users?role=${role}`);
            return response.data;
        },
        enabled: !!useAuthStore.getState().user?.school_id,
    });
}
export function useCurricula() {
    return useQuery({
        queryKey: ["curricula"],
        queryFn: async () => {
            const response = await apiClient.get("/api/v1/curricula");
            return response.data;
        },
    });
}
export function useGrades() {
    return useQuery({
        queryKey: ["grades"],
        queryFn: async () => {
            const response = await apiClient.get("/api/v1/grades");
            return response.data;
        },
    });
}
export function useInviteUser() {
    const queryClient = useQueryClient();
    const schoolId = getSchoolId();
    return useMutation({
        mutationFn: async (data) => {
            const response = await apiClient.post(`/api/v1/schools/${schoolId}/users`, data);
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
        mutationFn: async (data) => {
            const response = await apiClient.post(`/api/v1/schools/${schoolId}/classes`, data);
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
        mutationFn: async (data) => {
            const response = await apiClient.patch(`/api/v1/classes/${data.classId}`, data);
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
        mutationFn: async (data) => {
            const response = await apiClient.patch(`/api/v1/schools/${schoolId}/users/${data.userId}`, { status: data.status });
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["school", "users"] });
        },
    });
}
export function useEnrollStudents(classId) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data) => {
            const response = await apiClient.post(`/api/v1/classes/${classId}/enroll`, data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["school", "classes"] });
        },
    });
}
