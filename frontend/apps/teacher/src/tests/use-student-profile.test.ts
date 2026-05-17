// Tests for the data-shaping logic inside fetchStudentProfile.
// The pure shaping function is replicated below so no hooks are invoked.

describe("fetchStudentProfile data shaping", () => {
  test("test_fetch_student_profile_when_enrolled_in_teacher_class_then_derives_subject_and_class_name", () => {
    const raw = buildRawInfo({
      enrolledClasses: [
        {
          classId: "c1",
          className: "Grade 9 Math",
          subjectId: "sub1",
          subjectName: "Mathematics",
          gradeName: "Grade 9",
        },
      ],
    });
    const result = shapeStudentProfile("stu1", raw, null, ["c1"]);
    expect(result.studentName).toBe("Alice Smith");
    expect(result.gradeName).toBe("Grade 9");
    expect(result.className).toBe("Grade 9 Math");
    expect(result.availableSubjects).toEqual([
      { subjectId: "sub1", subjectName: "Mathematics" },
    ]);
  });

  test("test_fetch_student_profile_when_class_not_in_teacher_ids_then_excluded_from_subjects", () => {
    const raw = buildRawInfo({
      enrolledClasses: [
        {
          classId: "c1",
          className: "Grade 9 Math",
          subjectId: "sub1",
          subjectName: "Mathematics",
          gradeName: "Grade 9",
        },
        {
          classId: "c2",
          className: "Other Teacher Class",
          subjectId: "sub2",
          subjectName: "Biology",
          gradeName: "Grade 9",
        },
      ],
    });
    const result = shapeStudentProfile("stu1", raw, null, ["c1"]);
    expect(result.availableSubjects).toHaveLength(1);
    expect(result.availableSubjects[0].subjectName).toBe("Mathematics");
    expect(result.className).toBe("Grade 9 Math");
  });

  test("test_fetch_student_profile_when_two_classes_same_subject_then_deduplicates_subjects", () => {
    const raw = buildRawInfo({
      enrolledClasses: [
        {
          classId: "c1",
          className: "Math A",
          subjectId: "sub1",
          subjectName: "Mathematics",
          gradeName: "Grade 9",
        },
        {
          classId: "c2",
          className: "Math B",
          subjectId: "sub1",
          subjectName: "Mathematics",
          gradeName: "Grade 9",
        },
      ],
    });
    const result = shapeStudentProfile("stu1", raw, null, ["c1", "c2"]);
    expect(result.availableSubjects).toHaveLength(1);
  });

  test("test_fetch_student_profile_when_two_different_subjects_then_lists_both", () => {
    const raw = buildRawInfo({
      enrolledClasses: [
        {
          classId: "c1",
          className: "Math",
          subjectId: "sub1",
          subjectName: "Mathematics",
          gradeName: "Grade 9",
        },
        {
          classId: "c2",
          className: "Bio",
          subjectId: "sub2",
          subjectName: "Biology",
          gradeName: "Grade 9",
        },
      ],
    });
    const result = shapeStudentProfile("stu1", raw, null, ["c1", "c2"]);
    expect(result.availableSubjects).toHaveLength(2);
  });

  test("test_fetch_student_profile_when_no_enrolled_classes_then_empty_subjects_and_null_class_name", () => {
    const raw = buildRawInfo({ enrolledClasses: [] });
    const result = shapeStudentProfile("stu1", raw, null, []);
    expect(result.availableSubjects).toHaveLength(0);
    expect(result.className).toBeNull();
  });

  test("test_fetch_student_profile_when_learning_profile_present_then_passes_through", () => {
    const profile = {
      student_id: "stu1",
      modality_scores: {
        visual: 0.8,
        auditory: 0.3,
        reading_writing: 0.6,
        kinesthetic: 0.5,
      },
      work_style: { prefers_solo: true },
      interests: ["football"],
      completed_at: "2026-01-01T00:00:00Z",
    };
    const raw = buildRawInfo({ enrolledClasses: [] });
    const result = shapeStudentProfile("stu1", raw, profile, []);
    expect(result.learningProfile).toEqual(profile);
  });
});

// ── Helpers ──────────────────────────────────────────────────────────────────

interface FakeEnrolledClass {
  classId: string;
  className: string;
  subjectId: string;
  subjectName: string;
  gradeName: string;
}

function buildRawInfo(overrides: { enrolledClasses?: FakeEnrolledClass[] }) {
  return {
    id: "stu1",
    firstName: "Alice",
    lastName: "Smith",
    email: "alice@school.com",
    gradeName: "Grade 9",
    enrolledClasses: overrides.enrolledClasses ?? [],
  };
}

function shapeStudentProfile(
  studentId: string,
  info: ReturnType<typeof buildRawInfo>,
  learningProfile: unknown,
  teacherClassIds: string[],
) {
  const teacherClassIdSet = new Set(teacherClassIds);
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
    learningProfile: learningProfile ?? null,
    availableSubjects: Array.from(subjectMap.entries()).map(
      ([subjectId, subjectName]) => ({ subjectId, subjectName }),
    ),
  };
}
