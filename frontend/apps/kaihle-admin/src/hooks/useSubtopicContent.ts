import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types ──────────────────────────────────────────────────────────────────

export interface VideoEntry {
  url: string;
  title: string;
  channel: string;
  view_count: number | null;
  status: "pending" | "approved" | "rejected" | "stale";
  last_checked_at: string | null;
}

export interface VideoSection {
  content_id: string;
  videos: VideoEntry[];
  review_status: string;
  pending_count: number;
  approved_count: number;
}

export interface ExplanationSection {
  content_id: string;
  explanation_text: string | null;
  review_status: string;
  reviewed_at: string | null;
}

export interface QuizQuestionEntry {
  question_id: string;
  question_text: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  difficulty_level: number | null;
}

export interface QuizSection {
  content_id: string;
  questions: QuizQuestionEntry[];
  quiz_questions_count: number;
  review_status: string;
  reviewed_at: string | null;
}

export interface FullSubtopicContentReviewResponse {
  subtopic_id: string;
  subtopic_name: string;
  subject_code: string;
  grade_level: number;
  curriculum_code: string;
  learning_objective: string;
  video: VideoSection | null;
  explanation: ExplanationSection | null;
  quiz: QuizSection | null;
}

export interface ReviewQueueItem {
  subtopic_id: string;
  subtopic_name: string;
  subject_code: string;
  grade_level: number;
  pending_video_count: number;
  approved_video_count: number;
  video_status: string | null;
  explanation_status: string | null;
  quiz_status: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  pending_total: number;
}

export interface PromotionQueueItem {
  subtopic_content_id: string;
  subtopic_id: string;
  subtopic_name: string;
  topic_name: string;
  content_type: string;
  school_name: string;
  reviewed_by_name: string | null;
  subject_code: string;
  grade_level: number;
  review_status: string;
  reviewed_at: string | null;
  school_id: string;
  explanation_text: string | null;
  quiz_questions: Record<string, unknown>[] | null;
  interest_category_name: string | null;
}

export interface PromotionQueueResponse {
  items: PromotionQueueItem[];
  total: number;
}

export interface SuggestionQueueItem {
  suggestion_id: string;
  subtopic_content_id: string;
  subtopic_name: string;
  interest_category_name: string | null;
  teacher_name: string;
  original_text: string;
  suggested_text: string;
  status: string;
  created_at: string;
}

export interface SuggestionQueueResponse {
  items: SuggestionQueueItem[];
  total: number;
}

export interface ExplanationListResponse {
  subtopic_id: string;
  generic: ExplanationSection | null;
  personalised: ExplanationSection[];
}

export interface VideoStatusUpdateRequest {
  status: "approved" | "rejected";
}

export interface ManualVideoAddRequest {
  url: string;
  title: string;
  channel?: string;
}

export interface ExplanationUpdateRequest {
  explanation_text: string;
  review_status: "approved" | "rejected";
  rejection_reason?: string;
}

export interface QuizUpdateRequest {
  questions: QuizQuestionEntry[];
  review_status: "approved" | "rejected";
  rejection_reason?: string;
}

// ── Query keys ─────────────────────────────────────────────────────────────

const QUEUE_KEY = ["subtopic-content", "review-queue"] as const;
const detailKey = (id: string) => ["subtopic-content", id] as const;

// ── Hooks ──────────────────────────────────────────────────────────────────

export function useReviewQueue(params?: {
  subject?: string;
  grade?: number;
  status?: "all" | "pending" | "complete";
  page?: number;
  page_size?: number;
}) {
  const { subject, grade, status, page = 1, page_size = 20 } = params ?? {};

  return useQuery({
    queryKey: [...QUEUE_KEY, { subject, grade, status, page, page_size }],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (subject) searchParams.set("subject", subject);
      if (grade !== undefined) searchParams.set("grade", String(grade));
      if (status && status !== "all") searchParams.set("status", status);
      searchParams.set("page", String(page));
      searchParams.set("page_size", String(page_size));

      const response = await apiClient.get<ReviewQueueResponse>(
        `/api/v1/subtopic-content/review-queue?${searchParams.toString()}`,
      );
      return response.data;
    },
  });
}

export function useSubtopicContent(subtopicId: string) {
  return useQuery({
    queryKey: detailKey(subtopicId),
    queryFn: async () => {
      const response = await apiClient.get<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}`,
      );
      return response.data;
    },
    enabled: !!subtopicId,
  });
}

export function useUpdateVideoStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      subtopicId,
      videoIndex,
      status,
    }: {
      subtopicId: string;
      videoIndex: number;
      status: "approved" | "rejected";
    }) => {
      const response = await apiClient.patch<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/videos/${videoIndex}`,
        { status } as VideoStatusUpdateRequest,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.subtopic_id), data);
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}

export function useAddManualVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      subtopicId,
      payload,
    }: {
      subtopicId: string;
      payload: ManualVideoAddRequest;
    }) => {
      const response = await apiClient.post<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/videos`,
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.subtopic_id), data);
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}

export function useRefreshVideoCandidates() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (subtopicId: string) => {
      const response = await apiClient.post<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/videos/refresh`,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.subtopic_id), data);
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}

export function useUpdateExplanation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      subtopicId,
      payload,
    }: {
      subtopicId: string;
      payload: ExplanationUpdateRequest;
    }) => {
      const response = await apiClient.patch<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/explanation`,
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.subtopic_id), data);
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}

export function useGenerateQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (subtopicId: string) => {
      const response = await apiClient.post<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/quiz/admin-generate`,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.subtopic_id), data);
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}

export function useUpdateQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      subtopicId,
      payload,
    }: {
      subtopicId: string;
      payload: QuizUpdateRequest;
    }) => {
      const response = await apiClient.patch<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/quiz`,
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(detailKey(data.subtopic_id), data);
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}

// ── Promotion queue ─────────────────────────────────────────────────────────

const PROMOTION_KEY = ["subtopic-content", "promotion-queue"] as const;

export function usePromotionQueue(params?: {
  page?: number;
  page_size?: number;
}) {
  const { page = 1, page_size = 20 } = params ?? {};
  return useQuery({
    queryKey: [...PROMOTION_KEY, { page, page_size }],
    queryFn: async () => {
      const response = await apiClient.get<PromotionQueueResponse>(
        `/api/v1/subtopic-content/promotion-queue?page=${page}&page_size=${page_size}`,
      );
      return response.data;
    },
  });
}

export function usePromoteContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      contentId,
      action,
      rejectionReason,
    }: {
      contentId: string;
      action: "promote" | "reject_promotion";
      rejectionReason?: string;
    }) => {
      const response = await apiClient.patch(
        `/api/v1/subtopic-content/rows/${contentId}/promote`,
        { action, rejection_reason: rejectionReason ?? null },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROMOTION_KEY });
    },
  });
}

export function useEditContentRow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      contentId,
      explanationText,
    }: {
      contentId: string;
      explanationText: string;
    }) => {
      const response = await apiClient.patch(
        `/api/v1/subtopic-content/rows/${contentId}`,
        { explanation_text: explanationText },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROMOTION_KEY });
    },
  });
}

// ── Suggestions queue ───────────────────────────────────────────────────────

const SUGGESTIONS_KEY = ["subtopic-content", "suggestions"] as const;

export function useSuggestionsQueue(params?: {
  page?: number;
  page_size?: number;
}) {
  const { page = 1, page_size = 20 } = params ?? {};
  return useQuery({
    queryKey: [...SUGGESTIONS_KEY, { page, page_size }],
    queryFn: async () => {
      const qs = new URLSearchParams({
        page: String(page),
        page_size: String(page_size),
      });
      const response = await apiClient.get<SuggestionQueueResponse>(
        `/api/v1/subtopic-content/suggestions?${qs}`,
      );
      return response.data;
    },
  });
}

export function useReviewSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      suggestionId,
      action,
      finalText,
      adminNote,
    }: {
      suggestionId: string;
      action: "accept" | "reject" | "accept_with_edits";
      finalText?: string;
      adminNote?: string;
    }) => {
      const response = await apiClient.patch(
        `/api/v1/subtopic-content/suggestions/${suggestionId}`,
        {
          action,
          final_text: finalText ?? null,
          admin_note: adminNote ?? null,
        },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SUGGESTIONS_KEY });
    },
  });
}

// ── Personalised explanations ───────────────────────────────────────────────

export function useSubtopicExplanations(subtopicId: string) {
  return useQuery({
    queryKey: ["subtopic-content", subtopicId, "explanations"],
    queryFn: async () => {
      const response = await apiClient.get<ExplanationListResponse>(
        `/api/v1/subtopic-content/${subtopicId}/explanations`,
      );
      return response.data;
    },
    enabled: !!subtopicId,
  });
}

export function useUpdatePersonalisedExplanation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      subtopicId,
      payload,
    }: {
      subtopicId: string;
      payload: {
        explanation_text: string;
        review_status: "approved" | "rejected";
        rejection_reason?: string;
      };
    }) => {
      const response = await apiClient.patch<FullSubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/explanation`,
        payload,
      );
      return response.data;
    },
    onSuccess: (_data, { subtopicId }) => {
      queryClient.invalidateQueries({
        queryKey: ["subtopic-content", subtopicId, "explanations"],
      });
      queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    },
  });
}
