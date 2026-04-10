/**
 * Unit tests for assessment page logic.
 *
 * Tests cover:
 *   - MCQ option deselection when a new option is selected for the same question
 *   - Progress bar percentage calculation
 *   - Score ring mastery color derivation via getMasteryStyle
 *
 * These tests exercise pure logic — no DOM rendering required.
 */

import { getMasteryStyle } from "@kaihle/types";

// ─────────────────────────────────────────────────────────────
//  MCQ answer selection logic
//  (mirroring the handleSelect reducer used in TakeAssessmentPage)
// ─────────────────────────────────────────────────────────────

/** Simulates the answers state reducer in TakeAssessmentPage. */
function selectOption(
  prev: Record<string, string>,
  questionId: string,
  key: string,
): Record<string, string> {
  return { ...prev, [questionId]: key };
}

describe("MCQ option selection", () => {
  test("test_mcq_options_when_option_selected_then_others_deselected", () => {
    // Arrange: start with option A selected for question q1
    const initialAnswers: Record<string, string> = { q1: "A" };

    // Act: select option C for the same question
    const nextAnswers = selectOption(initialAnswers, "q1", "C");

    // Assert: only option C is now recorded for q1 (A is gone)
    expect(nextAnswers["q1"]).toBe("C");
    // The record only has one entry for q1 — the previous "A" is replaced
    expect(Object.values(nextAnswers).filter((v) => v === "A")).toHaveLength(0);
  });

  test("test_mcq_options_when_different_question_answered_then_other_question_unaffected", () => {
    // Arrange: q1 answered with B, q2 answered with D
    const initialAnswers: Record<string, string> = { q1: "B", q2: "D" };

    // Act: change q1 to A
    const nextAnswers = selectOption(initialAnswers, "q1", "A");

    // Assert: q2 is unchanged
    expect(nextAnswers["q1"]).toBe("A");
    expect(nextAnswers["q2"]).toBe("D");
  });
});

// ─────────────────────────────────────────────────────────────
//  Progress bar calculation
//  (mirrors the progressPct derivation in TakeAssessmentPage)
// ─────────────────────────────────────────────────────────────

function calculateProgressPct(
  answers: Record<string, string>,
  totalQuestions: number,
): number {
  if (totalQuestions === 0) return 0;
  return (Object.keys(answers).length / totalQuestions) * 100;
}

describe("Progress bar percentage", () => {
  test("test_progress_bar_when_3_of_10_answered_then_30_percent_filled", () => {
    const answers: Record<string, string> = {
      q1: "A",
      q2: "B",
      q3: "C",
    };
    const pct = calculateProgressPct(answers, 10);
    expect(pct).toBe(30);
  });

  test("test_progress_bar_when_no_answers_then_0_percent_filled", () => {
    const pct = calculateProgressPct({}, 10);
    expect(pct).toBe(0);
  });

  test("test_progress_bar_when_all_answered_then_100_percent_filled", () => {
    const answers: Record<string, string> = {
      q1: "A",
      q2: "B",
    };
    const pct = calculateProgressPct(answers, 2);
    expect(pct).toBe(100);
  });

  test("test_progress_bar_when_total_is_0_then_0_percent_filled", () => {
    const pct = calculateProgressPct({}, 0);
    expect(pct).toBe(0);
  });
});

// ─────────────────────────────────────────────────────────────
//  Score ring mastery color derivation
// ─────────────────────────────────────────────────────────────

describe("Score ring mastery color", () => {
  test("test_score_ring_when_mastery_0_6_then_uses_amber_color", () => {
    const style = getMasteryStyle(0.6);

    // 0.6 is in the Developing band (0.4–0.7)
    expect(style.label).toBe("Developing");
    expect(style.strokeColour).toBe("#f59e0b"); // brand-amber
    expect(style.dotClass).toBe("bg-brand-amber");
  });

  test("test_score_ring_when_mastery_above_0_7_then_uses_green_color", () => {
    const style = getMasteryStyle(0.8);

    expect(style.label).toBe("Strong");
    expect(style.strokeColour).toBe("#16a34a"); // brand-green
    expect(style.dotClass).toBe("bg-brand-green");
  });

  test("test_score_ring_when_mastery_below_0_4_then_uses_red_color", () => {
    const style = getMasteryStyle(0.2);

    expect(style.label).toBe("Needs Work");
    expect(style.strokeColour).toBe("#ef4444"); // brand-red
    expect(style.dotClass).toBe("bg-brand-red");
  });

  test("test_score_ring_when_score_is_null_then_uses_muted_color", () => {
    const style = getMasteryStyle(null);

    expect(style.label).toBe("Not assessed");
    expect(style.strokeColour).toBe("#9ca3af"); // brand-muted
  });
});
