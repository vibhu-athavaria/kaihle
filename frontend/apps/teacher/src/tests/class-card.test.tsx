/**
 * Unit tests for ClassCard component.
 * Covers: class name, subject, student count, mastery, quick links, View button,
 * skeleton rendering, and mastery color classes per band.
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ClassCard, ClassCardSkeleton } from "../pages/dashboard/ClassCard";

function renderWithRouter(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("ClassCard", () => {
  const defaultProps = {
    classId: "cls-1",
    className: "Grade 10 Math",
    subjectName: "Mathematics",
    gradeName: "Grade 10",
    studentCount: 28,
    avgMastery: 0.72,
  };

  test("test_class_card_when_rendered_then_shows_class_name_and_subject_dot", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("Grade 10 Math")).toBeInTheDocument();
    const dot = screen.getByText("Grade 10 Math").previousElementSibling;
    expect(dot).toHaveClass("bg-brand-primary");
  });

  test("test_class_card_when_rendered_then_shows_grade_badge", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("Grade 10")).toBeInTheDocument();
  });

  test("test_class_card_when_rendered_then_shows_student_count", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("28 students")).toBeInTheDocument();
  });

  test("test_class_card_when_single_student_then_shows_student_singular", () => {
    renderWithRouter(<ClassCard {...defaultProps} studentCount={1} />);
    expect(screen.getByText("1 student")).toBeInTheDocument();
  });

  test("test_class_card_when_strong_mastery_then_shows_strong_label_and_green_text", () => {
    renderWithRouter(<ClassCard {...defaultProps} avgMastery={0.85} />);
    expect(screen.getByText("Strong")).toBeInTheDocument();
    const pct = screen.getByText("85%");
    expect(pct).toHaveClass("text-brand-green-dark");
  });

  test("test_class_card_when_developing_mastery_then_shows_developing_label_and_amber_text", () => {
    renderWithRouter(<ClassCard {...defaultProps} avgMastery={0.55} />);
    expect(screen.getByText("Developing")).toBeInTheDocument();
    const pct = screen.getByText("55%");
    expect(pct).toHaveClass("text-brand-amber-dark");
  });

  test("test_class_card_when_needs_work_mastery_then_shows_needs_work_label_and_red_text", () => {
    renderWithRouter(<ClassCard {...defaultProps} avgMastery={0.25} />);
    expect(screen.getByText("Needs Work")).toBeInTheDocument();
    const pct = screen.getByText("25%");
    expect(pct).toHaveClass("text-brand-red-dark");
  });

  test("test_class_card_when_null_mastery_then_shows_not_assessed", () => {
    renderWithRouter(<ClassCard {...defaultProps} avgMastery={null} />);
    expect(screen.getByText("Not assessed")).toBeInTheDocument();
  });

  test("test_class_card_when_rendered_then_no_sub_links_only_view_class_button", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.queryByText("Gap Map")).not.toBeInTheDocument();
    expect(screen.queryByText("Assessments")).not.toBeInTheDocument();
    expect(screen.queryByText("Lesson Plans")).not.toBeInTheDocument();
    expect(screen.queryByText("Study Plan")).not.toBeInTheDocument();
    expect(screen.getByText("View Class")).toBeInTheDocument();
  });

  test("test_class_card_when_rendered_then_view_class_button_has_correct_href", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("View Class")).toHaveAttribute(
      "href",
      "/teacher/classes/cls-1",
    );
  });

  test("test_class_card_when_rendered_then_view_class_button_uses_gold_background", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("View Class")).toHaveClass("bg-brand-gold");
  });

  test("test_class_card_when_rendered_then_view_class_button_has_focus_visible_ring", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("View Class")).toHaveClass("focus-visible:ring-2");
  });

  test("test_class_card_when_rendered_then_view_class_button_is_full_width", () => {
    renderWithRouter(<ClassCard {...defaultProps} />);
    expect(screen.getByText("View Class")).toHaveClass("w-full");
  });

  test("test_class_card_skeleton_when_rendered_then_no_crash", () => {
    const { container } = render(<ClassCardSkeleton />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});
