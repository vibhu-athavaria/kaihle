import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ApprovedVideo {
  url: string;
  title: string;
  channel: string;
  view_count: number | null;
}

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

export interface QuizQuestion {
  question_id: string;
  question_text: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  difficulty_level: number | null;
}

export interface TeacherQuizQuestionsResponse {
  questions: QuizQuestion[];
  quiz_questions_count: number;
  review_status: string;
  scope: string;
}

export function useTeacherQuizQuestions(subtopicId: string | undefined) {
  return useQuery<TeacherQuizQuestionsResponse>({
    queryKey: ["teacher", "quiz-questions", subtopicId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/subtopic-content/${subtopicId}/quiz/questions`,
      );
      return res.data as TeacherQuizQuestionsResponse;
    },
    enabled: !!subtopicId,
  });
}

// ── Approved videos for a subtopic (student/teacher approved view) ─────────

export function useSubtopicVideos(subtopicId: string | undefined) {
  return useQuery<ApprovedVideo[]>({
    queryKey: ["subtopic-videos", subtopicId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/subtopic-content/${subtopicId}/videos`,
      );
      return res.data as ApprovedVideo[];
    },
    enabled: !!subtopicId,
  });
}

// ── All video candidates for teacher review (includes pending) ──────────────

export interface VideoCandidateEntry {
  url: string;
  title: string;
  channel: string;
  status: string;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  view_count?: number | null;
}

export function useSubtopicVideoCandidates(subtopicId: string | undefined) {
  return useQuery<VideoCandidateEntry[]>({
    queryKey: ["subtopic-video-candidates", subtopicId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/subtopic-content/${subtopicId}/video/candidates`,
      );
      return res.data as VideoCandidateEntry[];
    },
    enabled: !!subtopicId,
  });
}

export function useSelectVideo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      subtopicId,
      videoIndex,
    }: {
      subtopicId: string;
      videoIndex: number;
    }) => {
      await apiClient.patch(
        `/api/v1/subtopic-content/${subtopicId}/video/select`,
        { video_index: videoIndex },
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: statusKey(variables.subtopicId),
      });
      queryClient.invalidateQueries({
        queryKey: ["subtopic-video-candidates", variables.subtopicId],
      });
    },
  });
}

export function useSuggestVideo() {
  return useMutation({
    mutationFn: async ({
      subtopicId,
      message,
    }: {
      subtopicId: string;
      message: string;
    }) => {
      await apiClient.post(
        `/api/v1/subtopic-content/${subtopicId}/video/suggest`,
        { message },
      );
    },
  });
}

// ── Subtopics for a topic (lazy expand) ────────────────────────────────────

export interface SubtopicSimple {
  id: string;
  name: string;
}

export function useTopicSubtopics(
  topicId: string | null,
  filters?: { curriculumId?: string; gradeId?: string },
) {
  return useQuery<SubtopicSimple[]>({
    queryKey: [
      "topic-subtopics",
      topicId,
      filters?.curriculumId,
      filters?.gradeId,
    ],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (filters?.curriculumId) qs.set("curriculum_id", filters.curriculumId);
      if (filters?.gradeId) qs.set("grade_id", filters.gradeId);
      const res = await apiClient.get(
        `/api/v1/topics/${topicId}/subtopics?${qs.toString()}`,
      );
      return res.data as SubtopicSimple[];
    },
    enabled: !!topicId,
    staleTime: 5 * 60 * 1000,
  });
}
