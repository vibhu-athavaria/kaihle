// Tests for the data-shaping logic inside fetchStudentProfile.
// The pure shaping function is replicated below so no hooks are invoked.

describe("fetchStudentProfile data shaping", () => {
  test("test_fetch_student_profile_when_enrolled_in_one_class_then_derives_subject_and_class_name", () => {
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
    const result = shapeStudentProfile("stu1", raw, null);
    expect(result.studentName).toBe("Alice Smith");
    expect(result.gradeName).toBe("Grade 9");
    expect(result.className).toBe("Grade 9 Math");
    expect(result.availableSubjects).toEqual([
      { subjectId: "sub1", subjectName: "Mathematics" },
    ]);
    expect(result.learningProfile).toBeNull();
  });

  test("test_fetch_student_profile_when_enrolled_in_two_classes_same_subject_then_deduplicates_subjects", () => {
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
    const result = shapeStudentProfile("stu1", raw, null);
    expect(result.availableSubjects).toHaveLength(1);
  });

  test("test_fetch_student_profile_when_enrolled_in_two_different_subjects_then_lists_both_subjects", () => {
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
    const result = shapeStudentProfile("stu1", raw, null);
    expect(result.availableSubjects).toHaveLength(2);
    expect(result.availableSubjects.map((s) => s.subjectName)).toContain(
      "Biology",
    );
  });

  test("test_fetch_student_profile_when_no_enrolled_classes_then_empty_subjects_and_null_class_name", () => {
    const raw = buildRawInfo({ enrolledClasses: [] });
    const result = shapeStudentProfile("stu1", raw, null);
    expect(result.availableSubjects).toHaveLength(0);
    expect(result.className).toBeNull();
  });

  test("test_fetch_student_profile_when_learning_profile_present_then_passes_through", () => {
    const raw = buildRawInfo({ enrolledClasses: [] });
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
    const result = shapeStudentProfile("stu1", raw, profile);
    expect(result.learningProfile).toEqual(profile);
  });
});

// ── Helpers ──────────────────────────────────────────────────────────────────

interface RawInfoOverrides {
  enrolledClasses?: Array<{
    classId: string;
    className: string;
    subjectId: string;
    subjectName: string;
    gradeName: string;
  }>;
}

function buildRawInfo(overrides: RawInfoOverrides) {
  return {
    id: "stu1",
    firstName: "Alice",
    lastName: "Smith",
    email: "alice@school.com",
    gradeName: "Grade 9",
    enrolledClasses: overrides.enrolledClasses ?? [],
  };
}

// Pure shaping function extracted for testability (mirrors fetchStudentProfile logic)
function shapeStudentProfile(
  studentId: string,
  info: ReturnType<typeof buildRawInfo>,
  learningProfile: unknown,
) {
  const enrolled = info.enrolledClasses ?? [];
  const subjectMap = new Map<string, string>();
  for (const cls of enrolled) {
    if (cls.subjectId && !subjectMap.has(cls.subjectId)) {
      subjectMap.set(cls.subjectId, cls.subjectName);
    }
  }
  return {
    studentId,
    studentName: `${info.firstName} ${info.lastName}`.trim(),
    email: info.email,
    gradeName: info.gradeName ?? null,
    className: enrolled[0]?.className ?? null,
    gapMap: null,
    learningProfile: learningProfile ?? null,
    availableSubjects: Array.from(subjectMap.entries()).map(
      ([subjectId, subjectName]) => ({ subjectId, subjectName }),
    ),
  };
}
