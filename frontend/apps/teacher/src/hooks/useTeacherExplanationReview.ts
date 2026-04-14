import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface TeacherExplanationReviewItem {
  subtopic_content_id: string;
  subtopic_id: string;
  subtopic_name: string;
  explanation_text: string | null;
  teacher_explanation: string | null;
  review_status: "pending" | "approved" | "rejected";
  has_teacher_override: boolean;
}

export interface TeacherExplanationReviewDetail {
  subtopic_content_id: string;
  subtopic_id: string;
  subtopic_name: string;
  learning_objective: string;
  explanation_text: string | null;
  teacher_explanation: string | null;
  review_status: "pending" | "approved" | "rejected";
  has_teacher_override: boolean;
  applicable_tiers: number[];
}

export interface TeacherExplanationReviewListResponse {
  items: TeacherExplanationReviewItem[];
  total: number;
  pending_count: number;
}

export interface TeacherExplanationUpdateRequest {
  review_status?: "approved" | "rejected";
  teacher_explanation?: string;
}

export interface TeacherExplanationUpdateResponse {
  subtopic_content_id: string;
  review_status: string;
  teacher_explanation: string | null;
  has_teacher_override: boolean;
}

async function fetchExplanationReviewList(
  classId: string,
  status: string | null,
  page: number,
  pageSize: number,
): Promise<TeacherExplanationReviewListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await apiClient.get<TeacherExplanationReviewListResponse>(
    `/api/v1/teacher/classes/${classId}/explanation-review${query}`,
  );
  return res.data;
}

async function fetchExplanationReviewDetail(
  classId: string,
  subtopicId: string,
): Promise<TeacherExplanationReviewDetail> {
  const res = await apiClient.get<TeacherExplanationReviewDetail>(
    `/api/v1/teacher/classes/${classId}/explanation-review/${subtopicId}`,
  );
  return res.data;
}

async function updateExplanation(
  classId: string,
  subtopicId: string,
  body: TeacherExplanationUpdateRequest,
): Promise<TeacherExplanationUpdateResponse> {
  const res = await apiClient.patch<TeacherExplanationUpdateResponse>(
    `/api/v1/teacher/classes/${classId}/explanation-review/${subtopicId}`,
    body,
  );
  return res.data;
}

export function useExplanationReviewList(
  classId: string,
  status: string | null = null,
  page: number = 1,
  pageSize: number = 20,
) {
  return useQuery({
    queryKey: [
      "teacher",
      "explanation-review",
      classId,
      status,
      page,
      pageSize,
    ],
    queryFn: () => fetchExplanationReviewList(classId, status, page, pageSize),
    enabled: !!classId,
  });
}

export function useExplanationReviewDetail(
  classId: string,
  subtopicId: string,
) {
  return useQuery({
    queryKey: ["teacher", "explanation-review", classId, subtopicId],
    queryFn: () => fetchExplanationReviewDetail(classId, subtopicId),
    enabled: !!classId && !!subtopicId,
  });
}

export function useUpdateExplanation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      classId,
      subtopicId,
      body,
    }: {
      classId: string;
      subtopicId: string;
      body: TeacherExplanationUpdateRequest;
    }) => updateExplanation(classId, subtopicId, body),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["teacher", "explanation-review", variables.classId],
      });
    },
  });
}

// --- Teacher-wide hook for Content Review page ---

export type TeacherReviewStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface TeacherExplanationReviewWithClass {
  subtopicContentId: string;
  subtopicId: string;
  subtopicName: string;
  explanationText: string | null;
  teacherExplanation: string | null;
  reviewStatus: TeacherReviewStatus;
  hasTeacherOverride: boolean;
  classId: string;
  className: string;
  createdAt: string;
}

interface TeacherExplanationReviewResponse {
  subtopic_content_id: string;
  subtopic_id: string;
  subtopic_name: string;
  explanation_text: string | null;
  teacher_explanation: string | null;
  review_status: string;
  has_teacher_override: boolean;
  class_id: string;
  class_name: string;
  created_at: string;
}

async function fetchAllTeacherExplanationReview(
  status?: TeacherReviewStatus,
): Promise<TeacherExplanationReviewWithClass[]> {
  const params: Record<string, string> = {};
  if (status) {
    params.status = status.toLowerCase();
  }
  const res = await apiClient.get<TeacherExplanationReviewResponse[]>(
    `/api/v1/teachers/me/explanation-review`,
    { params },
  );
  return (res.data ?? []).map((item) => ({
    subtopicContentId: item.subtopic_content_id,
    subtopicId: item.subtopic_id,
    subtopicName: item.subtopic_name,
    explanationText: item.explanation_text,
    teacherExplanation: item.teacher_explanation,
    reviewStatus: item.review_status as TeacherReviewStatus,
    hasTeacherOverride: item.has_teacher_override,
    classId: item.class_id,
    className: item.class_name,
    createdAt: item.created_at,
  }));
}

export function useAllTeacherExplanationReview(status?: TeacherReviewStatus) {
  return useQuery({
    queryKey: ["teacher", "all-explanation-review", status],
    queryFn: () => fetchAllTeacherExplanationReview(status),
    staleTime: 30 * 1000,
  });
}
