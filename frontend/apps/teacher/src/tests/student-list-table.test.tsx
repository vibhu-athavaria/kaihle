import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StudentListTable } from "../components/students/StudentListTable";

function renderTable(
  students: Parameters<typeof StudentListTable>[0]["students"],
) {
  return render(
    <MemoryRouter>
      <StudentListTable students={students} />
    </MemoryRouter>,
  );
}

const baseStudent = {
  id: "stu-1",
  name: "Alice Smith",
  email: "alice@school.com",
  gradeName: "Grade 9",
  classIds: ["c1"],
  classNames: ["Math 9A"],
};

describe("StudentListTable", () => {
  test("test_student_list_table_when_grade_name_present_then_renders_grade", () => {
    renderTable([baseStudent]);
    expect(screen.getByText("Grade 9")).toBeInTheDocument();
  });

  test("test_student_list_table_when_grade_name_null_then_no_grade_shown", () => {
    renderTable([{ ...baseStudent, gradeName: null }]);
    expect(screen.queryByText(/Grade/)).not.toBeInTheDocument();
  });

  test("test_student_list_table_when_student_present_then_shows_name_and_email", () => {
    renderTable([baseStudent]);
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("alice@school.com")).toBeInTheDocument();
  });

  test("test_student_list_table_when_empty_then_shows_empty_state", () => {
    renderTable([]);
    expect(screen.getByText("No students yet")).toBeInTheDocument();
  });
});
