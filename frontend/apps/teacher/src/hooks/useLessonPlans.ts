import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

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

export interface ClassContextSnapshot {
  modality_distribution: Record<string, number>;
  top_interests: string[];
  student_count: number;
}

export interface LessonPlanMisconception {
  student_error: string;
  trigger_phrase: string;
  recovery_script: string;
}

export interface LessonPlanConcept {
  name: string;
  duration_minutes: number;
  teacher_does: string;
  student_does: string;
  check_question: string;
  misconception: LessonPlanMisconception;
  transition_cue: string | null;
}

export interface LessonPlanGroupActivity {
  description: string;
  stuck_prompt: string;
}

export interface LessonPlanExitTicketQuestion {
  label: string;
  question_text: string;
  good_answer: string;
  pivot_if_wrong: string;
}

export interface LessonPlanContent {
  lesson_hook: string;
  time_breakdown: {
    starter_minutes: number;
    intro_minutes: number;
    activity_minutes: number;
    exit_ticket_minutes: number;
    plenary_minutes: number;
  };
  learning_objectives: string[];
  key_concepts: LessonPlanConcept[];
  group_activities: {
    foundation: LessonPlanGroupActivity;
    core: LessonPlanGroupActivity;
    extension: LessonPlanGroupActivity;
  };
  resources_needed: string[];
  exit_ticket: {
    questions: LessonPlanExitTicketQuestion[];
  };
  starter: { duration_minutes: number; activity: string };
  plenary: { duration_minutes: number; activity: string };
  prior_knowledge: string;
  homework: string | null;
}

export interface LessonPlan {
  id: string;
  class_id: string;
  week_start: string | null;
  status: LessonPlanStatus;
  generated_plan: LessonPlanContent | null;
  teacher_edits: Partial<LessonPlanContent> | null;
  gap_summary: ClassContextSnapshot;
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

export function useClassLessonPlans(classId: string | undefined) {
  return useQuery({
    queryKey: ["lesson-plans", "class", classId],
    queryFn: () => fetchClassLessonPlans(classId!),
    enabled: !!classId,
  });
}

export function useLessonPlan(planId: string | undefined) {
  return useQuery({
    queryKey: ["lesson-plans", planId],
    queryFn: () => fetchLessonPlan(planId!),
    enabled: !!planId,
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
