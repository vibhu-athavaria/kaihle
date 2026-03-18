import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
function getSchoolId() {
    const user = JSON.parse(localStorage.getItem("auth_user") || "{}");
    return user.school_id || "default";
}
export function useSchoolAnalytics() {
    const schoolId = getSchoolId();
    return useQuery({
        queryKey: ["school-analytics", schoolId],
        queryFn: async () => {
            const { data } = await apiClient.get(`/api/v1/schools/${schoolId}/analytics`);
            return data;
        },
    });
}
export function useSchoolUsers(role) {
    const schoolId = getSchoolId();
    return useQuery({
        queryKey: ["school-users", schoolId, role],
        queryFn: async () => {
            const { data } = await apiClient.get(`/api/v1/schools/${schoolId}/users`, { params: { role } });
            return data;
        },
    });
}
export function useSchoolClasses() {
    const schoolId = getSchoolId();
    return useQuery({
        queryKey: ["school-classes", schoolId],
        queryFn: async () => {
            const { data } = await apiClient.get(`/api/v1/schools/${schoolId}/classes`);
            return data;
        },
    });
}
export function useCurricula() {
    return useQuery({
        queryKey: ["curricula"],
        queryFn: async () => {
            const { data } = await apiClient.get("/api/v1/curricula");
            return data;
        },
    });
}
export function useGrades() {
    return useQuery({
        queryKey: ["grades"],
        queryFn: async () => {
            const { data } = await apiClient.get("/api/v1/grades");
            return data;
        },
    });
}
export function useInviteUser() {
    const queryClient = useQueryClient();
    const schoolId = getSchoolId();
    return useMutation({
        mutationFn: async (payload) => {
            const { data } = await apiClient.post(`/api/v1/schools/${schoolId}/users`, payload);
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
        mutationFn: async (payload) => {
            const { data } = await apiClient.post(`/api/v1/schools/${schoolId}/classes`, payload);
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
        mutationFn: async ({ userId, ...payload }) => {
            const { data } = await apiClient.patch(`/api/v1/schools/${schoolId}/users/${userId}`, payload);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["school-users", schoolId] });
        },
    });
}
export function useEnrollStudents(classId) {
    const queryClient = useQueryClient();
    const schoolId = getSchoolId();
    return useMutation({
        mutationFn: async (payload) => {
            const { data } = await apiClient.post(`/api/v1/classes/${classId}/enroll`, payload);
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
        mutationFn: async ({ classId, ...payload }) => {
            const { data } = await apiClient.patch(`/api/v1/schools/${schoolId}/classes/${classId}`, payload);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["school-classes", schoolId] });
        },
    });
}
