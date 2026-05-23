import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types ──────────────────────────────────────────────────────────────────

export type ContentStatus =
  | "none"
  | "own_school_pending"
  | "other_school_pending"
  | "curriculum_pending"
  | "approved"
  | "rejected";

export interface ContentTypeStatus {
  status: ContentStatus;
  scope: "curriculum" | "school" | null;
  school_id: string | null;
}

export interface SubtopicContentStatusResponse {
  subtopic_id: string;
  video: ContentTypeStatus;
  explanation: ContentTypeStatus;
  quiz: ContentTypeStatus;
}

export interface PersonalisedExplanation {
  content_id: string;
  interest_category_id: string;
  interest_category_name: string;
  explanation_text: string | null;
  review_status: string;
}

export interface SubtopicExplanationsResponse {
  subtopic_id: string;
  generic: {
    content_id: string;
    explanation_text: string | null;
    review_status: string;
  } | null;
  personalised: PersonalisedExplanation[];
}

// ── Query keys ─────────────────────────────────────────────────────────────

const statusKey = (subtopicId: string) =>
  ["teacher", "subtopic-content-status", subtopicId] as const;

const explanationsKey = (subtopicId: string) =>
  ["teacher", "subtopic-explanations", subtopicId] as const;

// ── Hooks ──────────────────────────────────────────────────────────────────

export function useSubtopicContentStatus(subtopicId: string) {
  return useQuery({
    queryKey: statusKey(subtopicId),
    queryFn: async () => {
      const res = await apiClient.get<SubtopicContentStatusResponse>(
        `/api/v1/subtopic-content/${subtopicId}/status`,
      );
      return res.data;
    },
    enabled: !!subtopicId,
  });
}

export function useSubtopicExplanations(subtopicId: string) {
  return useQuery({
    queryKey: explanationsKey(subtopicId),
    queryFn: async () => {
      const res = await apiClient.get<SubtopicExplanationsResponse>(
        `/api/v1/subtopic-content/${subtopicId}/explanations`,
      );
      return res.data;
    },
    enabled: !!subtopicId,
  });
}

export function useTeacherGenerateContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      subtopicId,
      contentType,
    }: {
      subtopicId: string;
      contentType: "video" | "explanation" | "quiz";
    }) => {
      await apiClient.post(
        `/api/v1/subtopic-content/${subtopicId}/${contentType}/generate`,
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: statusKey(variables.subtopicId),
      });
    },
  });
}

export function useTeacherApproveContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      subtopicId,
      contentType,
      action,
    }: {
      subtopicId: string;
      contentType: "video" | "explanation" | "quiz";
      action: "approve" | "reject";
    }) => {
      await apiClient.patch(
        `/api/v1/subtopic-content/${subtopicId}/${contentType}/approve`,
        { action },
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: statusKey(variables.subtopicId),
      });
    },
  });
}

export function useSubmitExplanationSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      contentId,
      suggestedText,
    }: {
      contentId: string;
      suggestedText: string;
    }) => {
      await apiClient.post(`/api/v1/subtopic-content/${contentId}/suggest`, {
        suggested_text: suggestedText,
      });
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["teacher", "subtopic-explanations"],
        exact: false,
      });
      void variables;
    },
  });
}
