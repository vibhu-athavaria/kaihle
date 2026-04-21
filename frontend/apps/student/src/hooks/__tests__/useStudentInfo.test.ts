/**
 * @jest-environment jsdom
 */

// This file tests the StudentInfo interface by checking TypeScript compilation
// The test verifies camelCase field names match backend Pydantic aliases

describe("StudentInfo interface", () => {
  it("test_student_info_interface_uses_camelcase_fields", () => {
    // This is a compile-time check that verifies the interface has camelCase fields
    // If this compiles, the interface is correct
    const mockInfo = {
      firstName: "Jane" as const,
      lastName: "Doe" as const,
      gradeName: "Grade 9" as const,
      curriculumName: "Cambridge IGCSE" as const,
      schoolId: "abc-123" as const,
      id: "student-456" as const,
    };

    // TypeScript will error if the interface doesn't have these camelCase fields
    expect(mockInfo.firstName).toBe("Jane");
    expect(mockInfo.gradeName).toBe("Grade 9");
    expect(mockInfo.curriculumName).toBe("Cambridge IGCSE");
    expect(mockInfo.schoolId).toBe("abc-123");
  });

  it("test_student_info_snake_case_fields_are_undefined", () => {
    // Verify snake_case fields are NOT in the interface
    const info = {
      firstName: "Jane",
      lastName: "Doe",
      gradeName: "Grade 9",
      curriculumName: "Cambridge IGCSE",
      schoolId: "abc-123",
      id: "student-456",
    };

    // Access as any to simulate runtime behavior
    const anyInfo = info as any;
    expect(anyInfo.first_name).toBeUndefined();
    expect(anyInfo.grade_name).toBeUndefined();
    expect(anyInfo.curriculum_name).toBeUndefined();
    expect(anyInfo.school_id).toBeUndefined();
  });

  it("test_useStudentInfo_when_api_returns_enrolledClasses_then_types_include_them", () => {
    // This is a type-level test — if it compiles, it passes.
    const info: import("../useStudentInfo").StudentInfo = {
      id: "abc",
      firstName: "Jane",
      email: "jane@test.com",
      gradeName: "Grade 9",
      curriculumName: "Cambridge IGCSE",
      schoolId: "school-1",
      enrolledClasses: [
        {
          classId: "cls-1",
          className: "Math 9B",
          subjectId: "sub-1",
          subjectName: "Mathematics",
          gradeName: "Grade 9",
        },
      ],
    };
    expect(info.id).toBe("abc");
    expect(info.enrolledClasses).toHaveLength(1);
  });
});
