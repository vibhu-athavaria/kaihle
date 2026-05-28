import { useQuery } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";

export interface TeacherClassSummary {
  id: string;
  name: string;
  subjectId: string;
  subjectName: string;
  gradeId: string;
  gradeName: string;
  curriculumId: string;
  studentCount: number;
  avgMastery: number | null;
  studentsBelow: number;
}

interface ClassWithSummaryResponse {
  id: string;
  school_id: string;
  grade_id: string;
  subject_id: string;
  curriculum_id: string;
  teacher_id: string;
  name: string;
  academic_year: string;
  is_active: boolean;
  grade_name: string;
  subject_name: string;
  avg_mastery: number | null;
  student_count: number;
  students_below_threshold: number;
}

async function fetchTeacherClasses(
  schoolId: string,
  includeSummary: boolean | false,
): Promise<TeacherClassSummary[]> {
  const res = await apiClient.get<ClassWithSummaryResponse[]>(
    `/api/v1/schools/${schoolId}/classes`,
    { params: { include_summary: includeSummary || false } },
  );
  return (res.data ?? []).map((c) => ({
    id: c.id,
    name: c.name,
    subjectId: c.subject_id,
    subjectName: c.subject_name,
    gradeId: c.grade_id,
    gradeName: c.grade_name,
    curriculumId: c.curriculum_id,
    studentCount: c.student_count,
    avgMastery: c.avg_mastery,
    studentsBelow: c.students_below_threshold,
  }));
}

export function useTeacherClasses(
  schoolId: string | null,
  includeSummary: boolean | false,
) {
  // Include userId so teachers in the same school never share a cache entry.
  const userId = useAuthStore((state) => state.user?.id ?? null);
  return useQuery({
    queryKey: ["teacher", "classes-summary", schoolId, userId],
    queryFn: () => fetchTeacherClasses(schoolId!, includeSummary),
    enabled: !!schoolId,
    staleTime: 5 * 60 * 1000,
  });
}
