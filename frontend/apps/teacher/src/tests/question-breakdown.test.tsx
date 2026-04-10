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
    questionId: `q-${Math.random()}`,
    questionText: "What is 2 + 2?",
    selectedAnswer: "4",
    correctAnswer: "4",
    isCorrect: true,
    position: 1,
    ...overrides,
  };
}

function makeQuestions(count: number, allCorrect = true): QuestionAttempt[] {
  return Array.from({ length: count }, (_, i) =>
    makeQuestion({
      questionId: `q-${i}`,
      questionText: `Question ${i + 1}`,
      position: i + 1,
      isCorrect: allCorrect,
      selectedAnswer: allCorrect ? "4" : "3",
      correctAnswer: "4",
    }),
  );
}

describe("QuestionBreakdown", () => {
  test("test_correct_answer_when_is_correct_then_shows_only_answer_row", () => {
    const questions = [
      makeQuestion({
        isCorrect: true,
        selectedAnswer: "4",
        correctAnswer: "4",
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
        isCorrect: false,
        selectedAnswer: "3",
        correctAnswer: "4",
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
