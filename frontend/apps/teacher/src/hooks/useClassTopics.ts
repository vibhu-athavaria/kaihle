import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ClassTopicItem {
  id: string;
  class_id: string;
  curriculum_topic_id: string;
  topic_id: string;
  topic_name: string;
  subtopic_count: number;
  sequence_order: number;
  is_covered: boolean;
  mini_course_status: "none" | "generating" | "ready" | "failed";
}

export interface AvailableCurriculumTopic {
  curriculum_topic_id: string;
  topic_id: string;
  topic_name: string;
  subtopic_count: number;
  sequence_order: number;
}

// ── Queries ───────────────────────────────────────────────────────────────────

export function useClassTopics(classId: string | undefined) {
  return useQuery<ClassTopicItem[]>({
    queryKey: ["class", classId, "topics"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}/topics`);
      return res.data as ClassTopicItem[];
    },
    enabled: !!classId,
  });
}

export function useAvailableCurriculumTopics(classId: string | undefined) {
  return useQuery<AvailableCurriculumTopic[]>({
    queryKey: ["class", classId, "topics-available"],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/classes/${classId}/topics/available`,
      );
      return res.data as AvailableCurriculumTopic[];
    },
    enabled: !!classId,
  });
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useAddClassTopic(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      curriculum_topic_id: string;
      sequence_order: number;
    }) => {
      const res = await apiClient.post(
        `/api/v1/classes/${classId}/topics`,
        payload,
      );
      return res.data as ClassTopicItem;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["class", classId, "topics"] });
      queryClient.invalidateQueries({
        queryKey: ["class", classId, "topics-available"],
      });
    },
  });
}

export function useRemoveClassTopic(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (topicId: string) => {
      await apiClient.delete(`/api/v1/classes/${classId}/topics/${topicId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["class", classId, "topics"] });
      queryClient.invalidateQueries({
        queryKey: ["class", classId, "topics-available"],
      });
    },
  });
}

export function useUpdateClassTopic(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      topicId,
      is_covered,
      sequence_order,
    }: {
      topicId: string;
      is_covered?: boolean;
      sequence_order?: number;
    }) => {
      const res = await apiClient.put(
        `/api/v1/classes/${classId}/topics/${topicId}`,
        { is_covered, sequence_order },
      );
      return res.data as ClassTopicItem;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["class", classId, "topics"] });
    },
  });
}

export function useReorderClassTopics(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (items: { id: string; sequence_order: number }[]) => {
      const res = await apiClient.put(
        `/api/v1/classes/${classId}/topics/reorder`,
        { items: items.map((i) => [i.id, i.sequence_order]) },
      );
      return res.data as ClassTopicItem[];
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["class", classId, "topics"] });
    },
  });
}

export interface DesignTier1DiagnosticPayload {
  topic_ids: string[];
  questions_per_topic: number;
  time_limit_minutes: number | null;
  question_types: string[];
  minimum_difficulty: number;
  maximum_difficulty: number;
  deadline?: string | null;
}

export function useDesignTier1Diagnostic(classId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DesignTier1DiagnosticPayload) => {
      const res = await apiClient.post(
        `/api/v1/classes/${classId}/diagnostics/tier1`,
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["assessments", "class", classId],
      });
    },
  });
}
