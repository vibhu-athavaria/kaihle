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
  gradeName: string | null;
  className: string | null;
  gapMap: StudentGapMap | null;
  learningProfile: StudentLearningProfile | null;
  availableSubjects: Array<{ subjectId: string; subjectName: string }>;
}

interface EnrolledClassInfo {
  classId: string;
  className: string;
  subjectId: string;
  subjectName: string;
  gradeName: string;
}

interface StudentInfoApiResponse {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  gradeName: string;
  enrolledClasses: EnrolledClassInfo[];
}

async function fetchStudentProfile(
  studentId: string,
  teacherClassIds: string[],
): Promise<StudentProfileData> {
  const teacherClassIdSet = new Set(teacherClassIds);

  const [infoRes, profileRes] = await Promise.all([
    apiClient.get<StudentInfoApiResponse>(`/api/v1/students/${studentId}/info`),
    apiClient
      .get(`/api/v1/onboarding/learning-profile`, {
        params: { student_id: studentId },
      })
      .catch(() => ({ data: null })),
  ]);

  const info = infoRes.data;

  // Filter to only classes belonging to this teacher
  const teacherClasses = (info.enrolledClasses ?? []).filter(
    (cls) => teacherClassIdSet.size === 0 || teacherClassIdSet.has(cls.classId),
  );

  const subjectMap = new Map<string, string>();
  for (const cls of teacherClasses) {
    if (cls.subjectId && !subjectMap.has(cls.subjectId)) {
      subjectMap.set(cls.subjectId, cls.subjectName);
    }
  }

  return {
    studentId,
    studentName: `${info.firstName} ${info.lastName}`.trim(),
    email: info.email,
    gradeName: info.gradeName ?? null,
    className: teacherClasses[0]?.className ?? null,
    gapMap: null,
    learningProfile: profileRes.data,
    availableSubjects: Array.from(subjectMap.entries()).map(
      ([subjectId, subjectName]) => ({ subjectId, subjectName }),
    ),
  };
}

export function useStudentProfile(
  studentId: string | null,
  teacherClassIds: string[],
) {
  return useQuery({
    queryKey: [
      "teacher",
      "student-profile",
      studentId,
      teacherClassIds,
    ] as const,
    queryFn: () => fetchStudentProfile(studentId!, teacherClassIds),
    enabled: !!studentId,
    staleTime: 30 * 60 * 1000,
  });
}
