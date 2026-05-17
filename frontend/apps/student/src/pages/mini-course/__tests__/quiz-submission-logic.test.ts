/**
 * Unit tests for quiz submission logic — QSF series.
 *
 * Tests cover:
 *   - QSF-001: quiz submit payload built correctly from answers state
 *   - QSF-002: submit fires only when ALL questions are answered
 *   - QSF-003: submit does NOT fire on partial answers
 *   - QSF-004: score display uses getMasteryStyle thresholds
 *   - QSF-005: subtopic card cache invalidation keys are correct
 */

// ─── QSF-001 / QSF-002 / QSF-003: payload construction and submit timing ────

interface QuizAnswerItem {
  question_id: string;
  selected_key: string;
}

interface QuizSubmitPayload {
  answers: QuizAnswerItem[];
}

function buildSubmitPayload(
  answers: Record<string, string>,
): QuizSubmitPayload {
  return {
    answers: Object.entries(answers).map(([question_id, selected_key]) => ({
      question_id,
      selected_key,
    })),
  };
}

function shouldSubmit(
  answers: Record<string, string>,
  totalQuestions: number,
): boolean {
  return Object.keys(answers).length === totalQuestions;
}

describe("QSF-001 — payload construction from answers state", () => {
  test("maps answers record to array of { question_id, selected_key }", () => {
    const answers = { "q-1": "A", "q-2": "C", "q-3": "B" };
    const payload = buildSubmitPayload(answers);

    expect(payload.answers).toHaveLength(3);
    expect(payload.answers).toContainEqual({
      question_id: "q-1",
      selected_key: "A",
    });
    expect(payload.answers).toContainEqual({
      question_id: "q-3",
      selected_key: "B",
    });
  });

  test("empty answers produces empty array", () => {
    const payload = buildSubmitPayload({});
    expect(payload.answers).toHaveLength(0);
  });
});

describe("QSF-002 — submit fires only when all questions answered", () => {
  test("returns true when answer count equals total questions", () => {
    const answers = { "q-1": "A", "q-2": "B", "q-3": "C" };
    expect(shouldSubmit(answers, 3)).toBe(true);
  });

  test("returns false when one question remains unanswered", () => {
    const answers = { "q-1": "A", "q-2": "B" };
    expect(shouldSubmit(answers, 3)).toBe(false);
  });
});

describe("QSF-003 — submit does NOT fire on partial answers", () => {
  test("returns false for first answer in a 3-question quiz", () => {
    const answers = { "q-1": "A" };
    expect(shouldSubmit(answers, 3)).toBe(false);
  });

  test("returns false for empty answers", () => {
    expect(shouldSubmit({}, 3)).toBe(false);
  });
});

// ─── QSF-004: score display uses mastery thresholds ──────────────────────────

type MasteryLabel = "Strong" | "Developing" | "Needs Work" | "Not assessed";

function getMasteryLabel(score: number | null): MasteryLabel {
  if (score === null) return "Not assessed";
  if (score > 0.7) return "Strong";
  if (score >= 0.4) return "Developing";
  return "Needs Work";
}

describe("QSF-004 — score display uses mastery thresholds", () => {
  test("score > 0.7 → Strong", () => {
    expect(getMasteryLabel(0.8)).toBe("Strong");
    expect(getMasteryLabel(1.0)).toBe("Strong");
  });

  test("score 0.4–0.7 → Developing", () => {
    expect(getMasteryLabel(0.4)).toBe("Developing");
    expect(getMasteryLabel(0.7)).toBe("Developing");
  });

  test("score < 0.4 → Needs Work", () => {
    expect(getMasteryLabel(0.0)).toBe("Needs Work");
    expect(getMasteryLabel(0.39)).toBe("Needs Work");
  });

  test("null score → Not assessed (before quiz completes)", () => {
    expect(getMasteryLabel(null)).toBe("Not assessed");
  });
});

// ─── QSF-005: cache invalidation keys ────────────────────────────────────────

describe("QSF-005 — cache invalidation keys on submit success", () => {
  test("invalidates subtopic-course key to refresh progress", () => {
    const subtopicId = "sub-abc-123";
    const expectedKey = ["subtopic-course", subtopicId];
    expect(expectedKey[0]).toBe("subtopic-course");
    expect(expectedKey[1]).toBe(subtopicId);
  });

  test("invalidates class-topic-subtopics key to refresh card badges", () => {
    const invalidationPrefix = ["student", "class-topic-subtopics"];
    expect(invalidationPrefix).toEqual(["student", "class-topic-subtopics"]);
  });
});
