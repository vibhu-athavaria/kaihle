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

export interface SubtopicContentReviewResponse {
  subtopic_id: string;
  subtopic_name: string;
  subject_code: string;
  grade_level: number;
  curriculum_code: string;
  learning_objective: string;
  videos: VideoEntry[];
  pending_count: number;
  approved_count: number;
  explanation_review_status: string;
}

export interface ReviewQueueItem {
  subtopic_id: string;
  subtopic_name: string;
  subject_code: string;
  grade_level: number;
  pending_video_count: number;
  approved_video_count: number;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  pending_total: number;
}

export interface VideoStatusUpdateRequest {
  status: "approved" | "rejected";
}

export interface ManualVideoAddRequest {
  url: string;
  title: string;
  channel?: string;
}

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
    queryKey: [
      "subtopic-content",
      "review-queue",
      { subject, grade, status, page, page_size },
    ],
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
    queryKey: ["subtopic-content", subtopicId],
    queryFn: async () => {
      const response = await apiClient.get<SubtopicContentReviewResponse>(
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
      const response = await apiClient.patch<SubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/videos/${videoIndex}`,
        { status } as VideoStatusUpdateRequest,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["subtopic-content", data.subtopic_id], data);
      queryClient.invalidateQueries({
        queryKey: ["subtopic-content", "review-queue"],
      });
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
      const response = await apiClient.post<SubtopicContentReviewResponse>(
        `/api/v1/subtopic-content/${subtopicId}/videos`,
        payload,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["subtopic-content", data.subtopic_id], data);
      queryClient.invalidateQueries({
        queryKey: ["subtopic-content", "review-queue"],
      });
    },
  });
}
