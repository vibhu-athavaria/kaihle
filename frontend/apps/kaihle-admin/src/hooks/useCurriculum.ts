/**
 * React Query hooks for curriculum management.
 *
 * Provides CRUD operations for curricula, grades, subjects, topics, and subtopics.
 * All mutations invalidate relevant query keys for cache consistency.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

// =============================================================================
// Types
// =============================================================================

export interface Curriculum {
  id: string;
  name: string;
  code: string;
  description: string | null;
  country: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Grade {
  id: string;
  name: string;
  level: number;
  description: string | null;
  is_active: boolean;
  curriculum_ids: string[];
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  is_active: boolean;
}

export interface CurriculumSubject {
  curriculum_id: string;
  subject_id: string;
  subject_name: string;
  subject_code: string;
  is_core: boolean;
  sort_order: number | null;
}

export interface Topic {
  curriculum_topic_id: string;
  topic_id: string;
  name: string;
  canonical_code: string | null;
  standard_code: string | null;
  sequence_order: number | null;
  learning_objectives: string[];
  recommended_weeks: number | null;
  is_required: boolean;
  is_active: boolean;
  subtopic_count: number;
  grade_id: string | null;
  grade_name: string | null;
}

export interface Subtopic {
  id: string;
  curriculum_topic_id: string;
  name: string;
  canonical_code: string | null;
  learning_objective: string;
  description: string | null;
  keywords: string[] | null;
  bloom_taxonomy_level: string | null;
  difficulty_level: number | null;
  estimated_minutes: number | null;
  sequence_order: number | null;
  is_active: boolean;
}

// Create/Update types
export interface CurriculumCreate {
  name: string;
  code: string;
  description?: string;
  country?: string;
  is_active?: boolean;
}

export interface CurriculumUpdate {
  name?: string;
  code?: string;
  description?: string;
  country?: string;
  is_active?: boolean;
}

export interface GradeCreate {
  name: string;
  level: number;
  description?: string;
  is_active?: boolean;
  curriculum_ids?: string[];
}

export interface GradeUpdate {
  name?: string;
  level?: number;
  description?: string;
  is_active?: boolean;
  curriculum_ids?: string[];
}

export interface SubjectCreate {
  name: string;
  code: string;
  description?: string;
  icon?: string;
  color?: string;
  is_active?: boolean;
}

export interface SubjectUpdate {
  name?: string;
  code?: string;
  description?: string;
  icon?: string;
  color?: string;
  is_active?: boolean;
}

export interface LinkSubjectRequest {
  subject_id: string;
  is_core?: boolean;
  sort_order?: number;
}

export interface TopicIdentityCreate {
  name: string;
  canonical_code?: string;
  description?: string;
  keywords?: string[];
}

export interface CurriculumTopicCreate {
  topic_id?: string;
  topic_data?: TopicIdentityCreate;
  standard_code?: string;
  sequence_order?: number;
  learning_objectives?: string[];
  recommended_weeks?: number;
  is_required?: boolean;
}

export interface CurriculumTopicUpdate {
  standard_code?: string;
  sequence_order?: number;
  learning_objectives?: string[];
  recommended_weeks?: number;
  is_required?: boolean;
  is_active?: boolean;
}

export interface SubtopicCreate {
  name: string;
  learning_objective: string;
  canonical_code?: string;
  description?: string;
  keywords?: string[];
  bloom_taxonomy_level?: string;
  difficulty_level?: number;
  estimated_minutes?: number;
  sequence_order?: number;
}

export interface SubtopicUpdate {
  name?: string;
  learning_objective?: string;
  canonical_code?: string;
  description?: string;
  keywords?: string[];
  bloom_taxonomy_level?: string;
  difficulty_level?: number;
  estimated_minutes?: number;
  sequence_order?: number;
  is_active?: boolean;
}

// =============================================================================
// Read Hooks
// =============================================================================

export function useCurricula() {
  return useQuery({
    queryKey: ["curricula"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/curricula");
      return response.data as Curriculum[];
    },
  });
}

export function useGrades(curriculumId?: string) {
  return useQuery({
    queryKey: ["grades", { curriculumId }],
    queryFn: async () => {
      const params = curriculumId ? { curriculum_id: curriculumId } : {};
      const response = await apiClient.get("/api/v1/grades", { params });
      return response.data as Grade[];
    },
  });
}

export function useSubjects(curriculumId?: string) {
  return useQuery({
    queryKey: ["subjects", { curriculumId }],
    queryFn: async () => {
      const params = curriculumId ? { curriculum_id: curriculumId } : {};
      const response = await apiClient.get("/api/v1/subjects", { params });
      return response.data as Subject[];
    },
  });
}

export function useTopics(
  subjectId: string,
  curriculumId?: string,
  gradeId?: string,
) {
  return useQuery({
    queryKey: ["topics", { subjectId, curriculumId, gradeId }],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (curriculumId) params.curriculum_id = curriculumId;
      if (gradeId) params.grade_id = gradeId;
      const response = await apiClient.get(
        `/api/v1/subjects/${subjectId}/topics`,
        { params },
      );
      return response.data as Topic[];
    },
    enabled: !!subjectId,
  });
}

export function useSubtopics(
  topicId: string,
  curriculumId?: string,
  gradeId?: string,
) {
  return useQuery({
    queryKey: ["subtopics", { topicId, curriculumId, gradeId }],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (curriculumId) params.curriculum_id = curriculumId;
      if (gradeId) params.grade_id = gradeId;
      const response = await apiClient.get(
        `/api/v1/topics/${topicId}/subtopics`,
        { params },
      );
      return response.data as Subtopic[];
    },
    enabled: !!topicId,
  });
}

// =============================================================================
// Write Hooks - Curriculum
// =============================================================================

export function useCreateCurriculum() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CurriculumCreate) => {
      const response = await apiClient.post("/api/v1/curricula", data);
      return response.data as Curriculum;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["curricula"] });
    },
  });
}

export function useUpdateCurriculum() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: CurriculumUpdate;
    }) => {
      const response = await apiClient.patch(`/api/v1/curricula/${id}`, data);
      return response.data as Curriculum;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["curricula"] });
      queryClient.invalidateQueries({ queryKey: ["curriculum", variables.id] });
    },
  });
}

// =============================================================================
// Write Hooks - Grade
// =============================================================================

export function useCreateGrade() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: GradeCreate) => {
      const response = await apiClient.post("/api/v1/grades", data);
      return response.data as Grade;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grades"] });
    },
  });
}

export function useUpdateGrade() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: GradeUpdate }) => {
      const response = await apiClient.patch(`/api/v1/grades/${id}`, data);
      return response.data as Grade;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["grades"] });
      queryClient.invalidateQueries({ queryKey: ["grade", variables.id] });
    },
  });
}

// =============================================================================
// Write Hooks - Subject
// =============================================================================

export function useCreateSubject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: SubjectCreate) => {
      const response = await apiClient.post("/api/v1/subjects", data);
      return response.data as Subject;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subjects"] });
    },
  });
}

export function useUpdateSubject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: SubjectUpdate }) => {
      const response = await apiClient.patch(`/api/v1/subjects/${id}`, data);
      return response.data as Subject;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["subjects"] });
      queryClient.invalidateQueries({ queryKey: ["subject", variables.id] });
    },
  });
}

// =============================================================================
// Write Hooks - CurriculumSubject (Link/Unlink)
// =============================================================================

export function useLinkSubject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      curriculumId,
      data,
    }: {
      curriculumId: string;
      data: LinkSubjectRequest;
    }) => {
      const response = await apiClient.post(
        `/api/v1/curricula/${curriculumId}/subjects`,
        data,
      );
      return response.data as CurriculumSubject;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["subjects", { curriculumId: variables.curriculumId }],
      });
      queryClient.invalidateQueries({ queryKey: ["curricula"] });
    },
  });
}

export function useUnlinkSubject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      curriculumId,
      subjectId,
    }: {
      curriculumId: string;
      subjectId: string;
    }) => {
      await apiClient.delete(
        `/api/v1/curricula/${curriculumId}/subjects/${subjectId}`,
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["subjects", { curriculumId: variables.curriculumId }],
      });
      queryClient.invalidateQueries({ queryKey: ["curricula"] });
    },
  });
}

// =============================================================================
// Write Hooks - CurriculumTopic
// =============================================================================

export function useAddTopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      curriculumId,
      gradeId,
      subjectId,
      data,
    }: {
      curriculumId: string;
      gradeId: string;
      subjectId: string;
      data: CurriculumTopicCreate;
    }) => {
      const response = await apiClient.post(
        `/api/v1/curricula/${curriculumId}/grades/${gradeId}/subjects/${subjectId}/topics`,
        data,
      );
      return response.data as Topic;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [
          "topics",
          {
            subjectId: variables.subjectId,
            curriculumId: variables.curriculumId,
            gradeId: variables.gradeId,
          },
        ],
      });
    },
  });
}

export function useUpdateCurriculumTopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      ctId,
      data,
    }: {
      ctId: string;
      data: CurriculumTopicUpdate;
    }) => {
      const response = await apiClient.patch(
        `/api/v1/curriculum-topics/${ctId}`,
        data,
      );
      return response.data as Topic;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

export function useDeleteCurriculumTopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ctId: string) => {
      await apiClient.delete(`/api/v1/curriculum-topics/${ctId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

// =============================================================================
// Write Hooks - Subtopic
// =============================================================================

export function useCreateSubtopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      ctId,
      data,
    }: {
      ctId: string;
      data: SubtopicCreate;
    }) => {
      const response = await apiClient.post(
        `/api/v1/curriculum-topics/${ctId}/subtopics`,
        data,
      );
      return response.data as Subtopic;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subtopics"] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

export function useUpdateSubtopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: SubtopicUpdate }) => {
      const response = await apiClient.patch(`/api/v1/subtopics/${id}`, data);
      return response.data as Subtopic;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subtopics"] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

export function useDeleteSubtopic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/subtopics/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subtopics"] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}
