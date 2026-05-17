import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { SubjectMasteryCards } from "../components/students/SubjectMasteryCards";

describe("SubjectMasteryCards", () => {
  test("test_subject_mastery_cards_when_null_mastery_then_shows_dash_not_percentage", () => {
    render(
      <SubjectMasteryCards
        subjects={[
          { subjectId: "s1", subjectName: "Mathematics", avgMastery: null },
        ]}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  test("test_subject_mastery_cards_when_strong_mastery_then_shows_correct_percentage_and_label", () => {
    render(
      <SubjectMasteryCards
        subjects={[
          { subjectId: "s1", subjectName: "Mathematics", avgMastery: 0.82 },
        ]}
      />,
    );
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });

  test("test_subject_mastery_cards_when_developing_mastery_then_shows_correct_percentage_and_label", () => {
    render(
      <SubjectMasteryCards
        subjects={[
          { subjectId: "s1", subjectName: "Biology", avgMastery: 0.55 },
        ]}
      />,
    );
    expect(screen.getByText("55%")).toBeInTheDocument();
    expect(screen.getByText("Developing")).toBeInTheDocument();
  });

  test("test_subject_mastery_cards_when_needs_work_mastery_then_shows_correct_percentage_and_label", () => {
    render(
      <SubjectMasteryCards
        subjects={[
          { subjectId: "s1", subjectName: "Physics", avgMastery: 0.3 },
        ]}
      />,
    );
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(screen.getByText("Needs Work")).toBeInTheDocument();
  });

  test("test_subject_mastery_cards_when_boundary_score_0_7_then_shows_developing_not_strong", () => {
    render(
      <SubjectMasteryCards
        subjects={[
          { subjectId: "s1", subjectName: "Chemistry", avgMastery: 0.7 },
        ]}
      />,
    );
    expect(screen.getByText("Developing")).toBeInTheDocument();
  });

  test("test_subject_mastery_cards_when_multiple_subjects_then_renders_all_cards", () => {
    render(
      <SubjectMasteryCards
        subjects={[
          { subjectId: "s1", subjectName: "Mathematics", avgMastery: 0.85 },
          { subjectId: "s2", subjectName: "Biology", avgMastery: 0.45 },
          { subjectId: "s3", subjectName: "Chemistry", avgMastery: null },
        ]}
      />,
    );
    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("Biology")).toBeInTheDocument();
    expect(screen.getByText("Chemistry")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByText("45%")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  test("test_subject_mastery_cards_when_empty_subjects_then_renders_nothing", () => {
    const { container } = render(<SubjectMasteryCards subjects={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
