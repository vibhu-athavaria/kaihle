import { useQuery, useQueries } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface StudentRow {
  id: string;
  name: string;
  email: string;
  avgMastery: number | null;
  lastAssessedAt: string | null;
  dominantModality: string | null;
}

interface EnrollmentSummary {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

function getDominantModality(
  modalityScores: Record<string, number> | undefined,
): string | null {
  if (!modalityScores) return null;
  const entries = Object.entries(modalityScores);
  if (entries.length === 0) return null;
  return entries.reduce((max, curr) => (curr[1] > max[1] ? curr : max))[0];
}

export function useMyStudents(
  classId: string | null,
  subjectId: string | null,
) {
  const enrollmentsQuery = useQuery({
    queryKey: ["teacher", "enrollments", classId] as const,
    queryFn: async (): Promise<EnrollmentSummary[]> => {
      const res = await apiClient.get(`/api/v1/classes/${classId}/enrollments`);
      return res.data ?? [];
    },
    enabled: !!classId,
    staleTime: 5 * 60 * 1000,
  });

  const enrollments = enrollmentsQuery.data ?? [];

  const profileQueries = useQueries({
    queries: enrollments.map((e) => ({
      queryKey: ["teacher", "student-learning-profile", e.id] as const,
      queryFn: async () => {
        const res = await apiClient
          .get(`/api/v1/onboarding/learning-profile`, {
            params: { student_id: e.id },
          })
          .catch(() => ({ data: null }));
        return res.data;
      },
      staleTime: 10 * 60 * 1000,
    })),
  });

  const gapMapQuery = useQuery({
    queryKey: ["teacher", "class-gap-map", classId, subjectId] as const,
    queryFn: async () => {
      const res = await apiClient
        .get(`/api/v1/classes/${classId}/gap-map`, {
          params: { subject_id: subjectId },
        })
        .catch(() => ({ data: null }));
      return res.data;
    },
    enabled: !!classId && !!subjectId,
    staleTime: 5 * 60 * 1000,
  });

  const studentRows: StudentRow[] = enrollments.map((enrollment, index) => {
    const profile = profileQueries[index]?.data;
    const dominantModality = getDominantModality(profile?.modality_scores);

    let avgMastery: number | null = null;
    let lastAssessedAt: string | null = null;

    if (gapMapQuery.data?.nodes) {
      const scores: number[] = [];
      let latestDate: string | null = null;

      for (const node of gapMapQuery.data.nodes) {
        const studentScore = node.student_scores?.find(
          (s: any) => s.student_id === enrollment.id,
        );
        if (
          studentScore?.mastery_score !== null &&
          studentScore?.mastery_score !== undefined
        ) {
          scores.push(studentScore.mastery_score);
        }
        if (studentScore?.last_assessed_at) {
          if (!latestDate || studentScore.last_assessed_at > latestDate) {
            latestDate = studentScore.last_assessed_at;
          }
        }
      }

      avgMastery =
        scores.length > 0
          ? scores.reduce((a, b) => a + b, 0) / scores.length
          : null;
      lastAssessedAt = latestDate;
    }

    return {
      id: enrollment.id,
      name: `${enrollment.first_name} ${enrollment.last_name}`.trim(),
      email: enrollment.email,
      avgMastery,
      lastAssessedAt,
      dominantModality,
    };
  });

  const isLoading =
    enrollmentsQuery.isLoading ||
    (!!classId && !!subjectId && gapMapQuery.isLoading);

  return {
    data: studentRows,
    isLoading,
    isError: enrollmentsQuery.isError,
  };
}
