import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface StudentSubtopicScore {
  subtopic_id: string;
  subtopic_name: string;
  topic_id: string;
  topic_name: string;
  mastery_score: number | null;
  last_assessed_at: string | null;
}

export interface StudentGapMap {
  student_id: string;
  subject_id: string;
  generated_at: string;
  scores: StudentSubtopicScore[];
}

export interface StudentLearningProfile {
  student_id: string;
  modality_scores: {
    visual: number;
    auditory: number;
    reading_writing: number;
    kinesthetic: number;
  };
  work_style: {
    prefers_solo?: boolean;
    short_sessions?: boolean;
    task_based?: boolean;
    [key: string]: boolean | undefined;
  } | null;
  interests: string[];
  completed_at: string | null;
}

export interface StudentProfileData {
  studentId: string;
  studentName: string;
  email: string | null;
  className: string | null;
  gapMap: StudentGapMap | null;
  learningProfile: StudentLearningProfile | null;
  availableSubjects: Array<{ subjectId: string; subjectName: string }>;
}

async function fetchStudentProfile(
  studentId: string,
  schoolId: string,
): Promise<StudentProfileData> {
  const [classesRes, profileRes] = await Promise.all([
    apiClient
      .get(`/api/v1/schools/${schoolId}/classes`)
      .catch(() => ({ data: [] })),
    apiClient
      .get(`/api/v1/onboarding/learning-profile`, {
        params: { student_id: studentId },
      })
      .catch(() => ({ data: null })),
  ]);

  const allClasses: any[] = classesRes.data ?? [];

  // Cap parallel enrollment checks at 5 to avoid N+1 API explosion
  const enrollmentChecks = await Promise.all(
    allClasses.slice(0, 5).map(async (cls: any) => {
      const res = await apiClient
        .get(`/api/v1/classes/${cls.id}/enrollments`)
        .catch(() => ({ data: [] }));
      const students: any[] = res.data ?? [];
      const match = students.find((s: any) => s.id === studentId);
      return match ? { cls, student: match } : null;
    }),
  );

  const studentClasses = enrollmentChecks.filter(Boolean) as Array<{
    cls: any;
    student: any;
  }>;

  const studentName =
    studentClasses.length > 0
      ? `${studentClasses[0].student.first_name} ${studentClasses[0].student.last_name}`.trim()
      : "Unknown Student";
  const email =
    studentClasses.length > 0 ? studentClasses[0].student.email : null;
  const className =
    studentClasses.length > 0 ? studentClasses[0].cls.name : null;

  // Derive subjects from enrolled classes — NOT from gap map topic_ids
  const subjectMap = new Map<string, string>();
  for (const entry of studentClasses) {
    if (entry.cls.subject_id) {
      const subjectName =
        entry.cls.subject_name ?? entry.cls.subjectName ?? entry.cls.subject_id;
      subjectMap.set(entry.cls.subject_id, subjectName);
    }
  }
  const availableSubjects = Array.from(subjectMap.entries()).map(
    ([subjectId, subjectName]) => ({ subjectId, subjectName }),
  );

  return {
    studentId,
    studentName,
    email,
    className,
    gapMap: null,
    learningProfile: profileRes.data,
    availableSubjects,
  };
}

export function useStudentProfile(
  studentId: string | null,
  schoolId: string | null,
) {
  return useQuery({
    queryKey: ["teacher", "student-profile", studentId, schoolId] as const,
    queryFn: () => fetchStudentProfile(studentId!, schoolId!),
    enabled: !!studentId && !!schoolId,
    staleTime: 30 * 60 * 1000,
  });
}
