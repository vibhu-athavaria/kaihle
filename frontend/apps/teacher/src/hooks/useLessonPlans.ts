import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type LessonPlanStatus =
  | "GENERATING"
  | "GENERATED"
  | "EDITED"
  | "USED"
  | "ARCHIVED";

export interface LessonPlan {
  id: string;
  class_id: string;
  week_start: string | null;
  status: LessonPlanStatus;
  generated_plan: Record<string, string> | null;
  teacher_edits: Record<string, string> | null;
  generated_at: string;
  failure_code: string | null;
  failure_reason: string | null;
}

export interface LessonPlanPage {
  data: LessonPlan[];
  total: number;
  page: number;
  page_size: number;
}

async function fetchClassLessonPlans(classId: string): Promise<LessonPlanPage> {
  const res = await apiClient.get(
    `/api/v1/classes/${classId}/lesson-plans?page_size=20`,
  );
  return res.data;
}

async function fetchLessonPlan(planId: string): Promise<LessonPlan> {
  const res = await apiClient.get(`/api/v1/lesson-plans/${planId}`);
  return res.data;
}

async function generateLessonPlan(params: {
  classId: string;
  focusSubtopicIds: string[];
}): Promise<LessonPlan> {
  const res = await apiClient.post(
    `/api/v1/classes/${params.classId}/lesson-plans/generate`,
    { focus_subtopic_ids: params.focusSubtopicIds },
  );
  return res.data;
}

async function editLessonPlan(params: {
  planId: string;
  edits: Partial<Record<string, string>>;
}): Promise<LessonPlan> {
  const res = await apiClient.patch(
    `/api/v1/lesson-plans/${params.planId}`,
    params.edits,
  );
  return res.data;
}

async function regenerateLessonPlan(planId: string): Promise<LessonPlan> {
  const res = await apiClient.post(`/api/v1/lesson-plans/${planId}/regenerate`);
  return res.data;
}

async function updateLessonPlanStatus(params: {
  planId: string;
  status: "USED" | "ARCHIVED";
}): Promise<LessonPlan> {
  const res = await apiClient.patch(
    `/api/v1/lesson-plans/${params.planId}/status`,
    { status: params.status },
  );
  return res.data;
}

export function useClassLessonPlans(classId: string | undefined) {
  return useQuery({
    queryKey: ["lesson-plans", "class", classId],
    queryFn: () => fetchClassLessonPlans(classId!),
    enabled: !!classId,
    // Poll every 5s while any plan is still generating
    refetchInterval: (query) => {
      const plans = query.state.data?.data ?? [];
      return plans.some((p) => p.status === "GENERATING") ? 5000 : false;
    },
  });
}

export function useLessonPlan(planId: string | undefined) {
  return useQuery({
    queryKey: ["lesson-plans", planId],
    queryFn: () => fetchLessonPlan(planId!),
    enabled: !!planId,
    refetchInterval: (query) => {
      return query.state.data?.status === "GENERATING" ? 5000 : false;
    },
  });
}

export function useGenerateLessonPlan(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: generateLessonPlan,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["lesson-plans", "class", classId],
      });
    },
  });
}

export function useEditLessonPlan(planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: editLessonPlan,
    onSuccess: (data) => {
      queryClient.setQueryData(["lesson-plans", planId], data);
      void queryClient.invalidateQueries({
        queryKey: ["lesson-plans", "class", data.class_id],
      });
    },
  });
}

export function useRegenerateLessonPlan(planId: string, classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => regenerateLessonPlan(planId),
    onSuccess: (data) => {
      queryClient.setQueryData(["lesson-plans", planId], data);
      void queryClient.invalidateQueries({
        queryKey: ["lesson-plans", "class", classId],
      });
    },
  });
}

export function useUpdateLessonPlanStatus(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateLessonPlanStatus,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["lesson-plans", "class", classId],
      });
    },
  });
}
