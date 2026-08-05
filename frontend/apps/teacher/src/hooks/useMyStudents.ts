import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiClient } from "@kaihle/auth";

export interface StudentRow {
  id: string;
  name: string;
  email: string;
  avgMastery: number | null;
  lastAssessedAt: string | null;
  dominantModality: string | null;
  classIds: string[];
}

interface EnrollmentSummary {
  id: string;
  // null for username-based students registered without an email address
  email: string | null;
  username: string | null;
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

export function useMyStudents(classIds: string[], subjectIds: string[]) {
  // Stable query configuration using useMemo to prevent recreating queries on each render
  const classIdSubjectPairs = useMemo(
    () =>
      classIds
        .map((classId, index) => ({
          classId,
          subjectId: subjectIds[index] ?? "",
        }))
        .filter((pair) => pair.classId && pair.subjectId),
    [classIds, subjectIds],
  );

  const enrollmentQueries = useQueries({
    queries: classIdSubjectPairs.map((pair) => ({
      queryKey: ["teacher", "enrollments", pair.classId] as const,
      queryFn: async (): Promise<EnrollmentSummary[]> => {
        const res = await apiClient.get(
          `/api/v1/classes/${pair.classId}/enrollments`,
        );
        return res.data ?? [];
      },
      enabled: classIdSubjectPairs.length > 0,
      staleTime: 10 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnMount: false,
    })),
  });

  const allEnrollments = classIdSubjectPairs.flatMap((pair, classIndex) =>
    (enrollmentQueries[classIndex].data ?? []).map((e) => ({
      ...e,
      classId: pair.classId,
      subjectId: pair.subjectId,
    })),
  );

  // Memoize unique student IDs to prevent profile query recreation
  const uniqueStudentIds = useMemo(
    () => [...new Set(allEnrollments.map((e) => e.id))],
    [allEnrollments],
  );

  const profileQueries = useQueries({
    queries: uniqueStudentIds.map((studentId) => ({
      queryKey: ["teacher", "student-learning-profile", studentId] as const,
      queryFn: async () => {
        const res = await apiClient
          .get(`/api/v1/onboarding/learning-profile`, {
            params: { student_id: studentId },
          })
          .catch(() => ({ data: null }));
        return res.data;
      },
      staleTime: 10 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnMount: false,
    })),
  });

  const profileMap = new Map<string, Record<string, any> | null>();
  uniqueStudentIds.forEach((studentId, index) => {
    profileMap.set(studentId, profileQueries[index]?.data ?? null);
  });

  const gapMapQueries = useQueries({
    queries: classIdSubjectPairs.map((pair) => ({
      queryKey: [
        "teacher",
        "class-gap-map",
        pair.classId,
        pair.subjectId,
      ] as const,
      queryFn: async () => {
        const res = await apiClient
          .get(`/api/v1/classes/${pair.classId}/gap-map`, {
            params: { subject_id: pair.subjectId },
          })
          .catch(() => ({ data: null }));
        return res.data;
      },
      enabled:
        classIdSubjectPairs.length > 0 && !!pair.classId && !!pair.subjectId,
      staleTime: 10 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnMount: false,
    })),
  });

  const gapMapByClass = new Map<string, any>();
  classIdSubjectPairs.forEach((pair, index) => {
    gapMapByClass.set(pair.classId, gapMapQueries[index]?.data ?? null);
  });

  const studentRows: StudentRow[] = uniqueStudentIds.map((studentId) => {
    const profile = profileMap.get(studentId) ?? null;
    const dominantModality = getDominantModality(profile?.modality_scores);

    let totalMastery = 0;
    let masteryCount = 0;
    let latestDate: string | null = null;

    const studentClasses = allEnrollments.filter((e) => e.id === studentId);
    for (const { classId } of studentClasses) {
      const gapMap = gapMapByClass.get(classId);
      if (gapMap?.nodes) {
        for (const node of gapMap.nodes) {
          const studentScore = node.student_scores?.find(
            (s: any) => s.student_id === studentId,
          );
          if (
            studentScore?.mastery_score !== null &&
            studentScore?.mastery_score !== undefined
          ) {
            totalMastery += studentScore.mastery_score;
            masteryCount++;
          }
          if (studentScore?.last_assessed_at) {
            if (!latestDate || studentScore.last_assessed_at > latestDate) {
              latestDate = studentScore.last_assessed_at;
            }
          }
        }
      }
    }

    const avgMastery = masteryCount > 0 ? totalMastery / masteryCount : null;

    const enrollment = allEnrollments.find((e) => e.id === studentId);
    const studentClassIds = [
      ...new Set(
        allEnrollments.filter((e) => e.id === studentId).map((e) => e.classId),
      ),
    ];

    return {
      id: studentId,
      name: enrollment
        ? `${enrollment.first_name} ${enrollment.last_name}`.trim()
        : studentId,
      email: enrollment?.email ?? enrollment?.username ?? "",
      avgMastery,
      lastAssessedAt: latestDate,
      dominantModality,
      classIds: studentClassIds,
    };
  });

  const isLoading =
    enrollmentQueries.some((q) => q.isLoading) ||
    gapMapQueries.some((q) => q.isLoading);

  return {
    data: studentRows,
    isLoading,
    isError: enrollmentQueries.some((q) => q.isError),
  };
}
