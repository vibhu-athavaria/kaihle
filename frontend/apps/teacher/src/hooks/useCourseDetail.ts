import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface InterestCategoryMeta {
  id: string;
  name: string;
  label: string;
}

export interface SubtopicVariant {
  content_id: string;
  explanation_text: string;
  review_status: "pending" | "approved" | "rejected";
  interest_label: string;
}

export interface SubtopicCourseDetail {
  subtopic_id: string;
  subtopic_name: string;
  sequence_order: number;
  variants: Record<string, SubtopicVariant | null>;
}

export interface StudentCourseAssignment {
  student_id: string;
  student_name: string;
  email: string;
  auto_interest_category: string | null;
  override_interest_category: string | null;
  effective_interest_category: string | null;
  override_id: string | null;
}

export interface CourseDetailResponse {
  topic_id: string;
  topic_name: string;
  subtopics: SubtopicCourseDetail[];
  students: StudentCourseAssignment[];
  interest_categories: InterestCategoryMeta[];
}

/**
 * GET /api/v1/classes/{classId}/topics/{topicId}/course-detail
 * Returns 4-variant course detail + student assignments for the teacher Course Detail page.
 */
export function useCourseDetail(
  classId: string | null,
  topicId: string | null,
) {
  return useQuery<CourseDetailResponse>({
    queryKey: ["course-detail", classId, topicId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/classes/${classId}/topics/${topicId}/course-detail`,
      );
      return res.data as CourseDetailResponse;
    },
    enabled: !!classId && !!topicId,
    staleTime: 30_000,
  });
}

/**
 * PATCH /api/v1/topics/{topicId}/variants/{contentId}/review
 * Approve or reject a specific interest-category variant.
 */
export function useReviewVariant(classId: string, topicId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      content_id: string;
      review_status: "approved" | "rejected";
      teacher_note?: string;
      edited_text?: string;
    }) => {
      const res = await apiClient.patch(
        `/api/v1/topics/${topicId}/variants/${payload.content_id}/review`,
        {
          review_status: payload.review_status,
          ...(payload.teacher_note
            ? { teacher_note: payload.teacher_note }
            : {}),
          ...(payload.edited_text ? { edited_text: payload.edited_text } : {}),
        },
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["course-detail", classId, topicId],
      });
    },
  });
}

/**
 * POST /api/v1/classes/{classId}/topics/{topicId}/student-overrides
 * Set or clear the interest-category override for a student.
 */
export function useSetStudentOverride(classId: string, topicId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      student_id: string;
      interest_category_id: string | null;
    }) => {
      const res = await apiClient.post(
        `/api/v1/classes/${classId}/topics/${topicId}/student-overrides`,
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["course-detail", classId, topicId],
      });
    },
  });
}
