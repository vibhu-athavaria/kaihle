import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import type {
  LessonPlanContent,
  LessonPlanConcept,
  LessonPlanGroupActivity,
  LessonPlanExitTicketQuestion,
  LessonPlanMisconception,
  ClassContextSnapshot,
} from "@kaihle/types";

export type {
  LessonPlanContent,
  LessonPlanConcept,
  LessonPlanGroupActivity,
  LessonPlanExitTicketQuestion,
  LessonPlanMisconception,
  ClassContextSnapshot,
};

export type LessonPlanStatus =
  | "GENERATING"
  | "GENERATED"
  | "EDITED"
  | "USED"
  | "ARCHIVED";

export interface SubtopicContext {
  subtopic_id: string;
  name: string;
  topic_name: string;
}

export interface LessonPlan {
  id: string;
  class_id: string;
  class_name: string;
  /** null when the class has no grade assigned — fall back to class_name */
  grade_name: string | null;
  week_start: string | null;
  status: LessonPlanStatus;
  duration_minutes: number;
  generated_plan: LessonPlanContent | null;
  teacher_edits: Partial<LessonPlanContent> | null;
  class_context_snapshot: ClassContextSnapshot | null;
  focus_subtopics: SubtopicContext[];
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

async function fetchClassLessonPlans(
  classId: string,
  page: number,
  pageSize: number,
): Promise<LessonPlanPage> {
  const res = await apiClient.get(
    `/api/v1/classes/${classId}/lesson-plans?page=${page}&page_size=${pageSize}`,
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
  durationMinutes: number;
}): Promise<LessonPlan> {
  const res = await apiClient.post(
    `/api/v1/classes/${params.classId}/lesson-plans/generate`,
    {
      focus_subtopic_ids: params.focusSubtopicIds,
      duration_minutes: params.durationMinutes,
    },
  );
  return res.data;
}

async function editLessonPlan(params: {
  planId: string;
  edits: Partial<LessonPlanContent>;
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

async function fetchTeacherLessonPlans(
  page: number,
  pageSize: number,
  classId?: string,
): Promise<LessonPlanPage> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (classId) params.class_id = classId;
  const res = await apiClient.get("/api/v1/lesson-plans", { params });
  return res.data;
}

export function useTeacherLessonPlans(
  page = 1,
  pageSize = 10,
  classId?: string,
) {
  return useQuery({
    queryKey: ["lesson-plans", "all", page, pageSize, classId],
    queryFn: () => fetchTeacherLessonPlans(page, pageSize, classId),
    refetchInterval: (query) => {
      const plans = query.state.data?.data ?? [];
      return plans.some((p) => p.status === "GENERATING") ? 5000 : false;
    },
  });
}

export function useClassLessonPlans(
  classId: string | undefined,
  page = 1,
  pageSize = 10,
) {
  return useQuery({
    queryKey: ["lesson-plans", "class", classId, page, pageSize],
    queryFn: () => fetchClassLessonPlans(classId!, page, pageSize),
    enabled: !!classId,
    // Poll while any plan is generating so failure/success surfaces immediately
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
  });
}

export function useGenerateLessonPlan(classId: string, onSuccess?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: generateLessonPlan,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["lesson-plans", "class", classId],
      });
      void queryClient.invalidateQueries({ queryKey: ["lesson-plans", "all"] });
      onSuccess?.();
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
      void queryClient.invalidateQueries({ queryKey: ["lesson-plans", "all"] });
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
      void queryClient.invalidateQueries({ queryKey: ["lesson-plans", "all"] });
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
      void queryClient.invalidateQueries({ queryKey: ["lesson-plans", "all"] });
    },
  });
}
