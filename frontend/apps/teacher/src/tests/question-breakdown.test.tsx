/**
 * Unit tests for QuestionBreakdown component.
 * Tests correct/wrong answer display and pagination behavior.
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuestionBreakdown } from "../components/results/QuestionBreakdown";
import type { QuestionAttempt } from "../hooks/useAssessmentResults";

function makeQuestion(
  overrides: Partial<QuestionAttempt> = {},
): QuestionAttempt {
  return {
    question_id: `q-${Math.random()}`,
    question_text: "What is 2 + 2?",
    subtopic_name: "Arithmetic",
    topic_name: "Numbers",
    difficulty_level: 2,
    selected_key: "A",
    correct_answer: "A",
    is_correct: true,
    position: 1,
    ...overrides,
  };
}

function makeQuestions(count: number, allCorrect = true): QuestionAttempt[] {
  return Array.from({ length: count }, (_, i) =>
    makeQuestion({
      question_id: `q-${i}`,
      question_text: `Question ${i + 1}`,
      position: i + 1,
      is_correct: allCorrect,
      selected_key: allCorrect ? "A" : "B",
      correct_answer: "A",
    }),
  );
}

describe("QuestionBreakdown", () => {
  test("test_correct_answer_when_is_correct_then_shows_only_answer_row", () => {
    const questions = [
      makeQuestion({
        is_correct: true,
        selected_key: "A",
        correct_answer: "A",
      }),
    ];
    render(<QuestionBreakdown questions={questions} />);

    // "Answer: X ✓" row must appear
    expect(screen.getByText("Answer:")).toBeInTheDocument();
    // "Given:" and "Correct:" rows must NOT appear for a correct answer
    expect(screen.queryByText("Given:")).not.toBeInTheDocument();
    expect(screen.queryByText("Correct:")).not.toBeInTheDocument();
  });

  test("test_wrong_answer_when_is_incorrect_then_shows_given_and_correct_rows", () => {
    const questions = [
      makeQuestion({
        is_correct: false,
        selected_key: "B",
        correct_answer: "A",
      }),
    ];
    render(<QuestionBreakdown questions={questions} />);

    // "Given: X ✕" row must appear
    expect(screen.getByText("Given:")).toBeInTheDocument();
    // "Correct: X ✓" row must also appear
    expect(screen.getByText("Correct:")).toBeInTheDocument();
    // "Answer:" row must NOT appear (it's for correct answers only)
    expect(screen.queryByText("Answer:")).not.toBeInTheDocument();
  });

  test("test_subtopic_chip_when_rendered_then_shows_subtopic_name", () => {
    const questions = [makeQuestion({ subtopic_name: "Linear Equations" })];
    render(<QuestionBreakdown questions={questions} />);
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();
  });

  test("test_difficulty_dots_when_difficulty_3_then_3_filled_dots_rendered", () => {
    const questions = [makeQuestion({ difficulty_level: 3 })];
    render(<QuestionBreakdown questions={questions} />);
    // aria-label on the dots container
    expect(screen.getByLabelText("Difficulty 3 of 5")).toBeInTheDocument();
  });

  test("test_pagination_when_6_or_fewer_questions_then_no_expand_button", () => {
    const questions = makeQuestions(6);
    render(<QuestionBreakdown questions={questions} />);

    expect(screen.queryByText(/more question/)).not.toBeInTheDocument();
  });

  test("test_pagination_when_7_questions_then_expand_button_shows_count", () => {
    const questions = makeQuestions(7);
    render(<QuestionBreakdown questions={questions} />);

    // Button shows "+ 1 more question" (7 - 6 = 1)
    expect(screen.getByText("+ 1 more question")).toBeInTheDocument();
    // Only first 6 questions visible initially
    expect(screen.getByText("Question 1")).toBeInTheDocument();
    expect(screen.getByText("Question 6")).toBeInTheDocument();
    expect(screen.queryByText("Question 7")).not.toBeInTheDocument();
  });

  test("test_pagination_when_expand_clicked_then_all_questions_visible", () => {
    const questions = makeQuestions(9);
    render(<QuestionBreakdown questions={questions} />);

    fireEvent.click(screen.getByText("+ 3 more questions"));

    // All 9 questions now visible
    expect(screen.getByText("Question 9")).toBeInTheDocument();
    // Expand button gone, "Show less" button present
    expect(screen.queryByText(/more question/)).not.toBeInTheDocument();
    expect(screen.getByText("Show less")).toBeInTheDocument();
  });

  test("test_pagination_when_show_less_clicked_then_first_6_only_visible", () => {
    const questions = makeQuestions(9);
    render(<QuestionBreakdown questions={questions} />);

    fireEvent.click(screen.getByText("+ 3 more questions"));
    fireEvent.click(screen.getByText("Show less"));

    expect(screen.queryByText("Question 7")).not.toBeInTheDocument();
    expect(screen.getByText("+ 3 more questions")).toBeInTheDocument();
  });

  test("test_empty_state_when_no_questions_then_shows_empty_message", () => {
    render(<QuestionBreakdown questions={[]} />);

    expect(screen.getByText("No answers submitted yet.")).toBeInTheDocument();
  });
});
