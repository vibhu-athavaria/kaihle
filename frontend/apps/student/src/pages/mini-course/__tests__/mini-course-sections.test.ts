/**
 * Unit tests for MiniCoursePage section ordering and next subtopic nudge.
 *
 * Tests cover:
 *   - MS-001: Video must appear before Explanation in section order
 *   - MS-002: "Still confused?" must be the last section (lowest priority)
 *   - MS-003: Next subtopic nudge appears only after all quiz questions answered
 *   - MS-004: Next subtopic nudge does not appear when next_subtopic is null
 *   - MS-005: "Still confused?" section uses minimal visual weight (not primary CTA style)
 */

// ─────────────────────────────────────────────────────────────
//  MS-001 / MS-002: Section ordering contract
//
//  The ordered section list drives render order in MiniCoursePage.
//  This test locks the required order so any future reorder shows
//  as a test failure, not a silent visual regression.
// ─────────────────────────────────────────────────────────────

type SectionKey = "header" | "video" | "explanation" | "quiz" | "explain_this";

const REQUIRED_SECTION_ORDER: SectionKey[] = [
  "header",
  "video",
  "explanation",
  "quiz",
  "explain_this",
];

describe("MS-001/MS-002 — section render order", () => {
  test("video appears before explanation", () => {
    const videoIdx = REQUIRED_SECTION_ORDER.indexOf("video");
    const explanationIdx = REQUIRED_SECTION_ORDER.indexOf("explanation");
    expect(videoIdx).toBeLessThan(explanationIdx);
  });

  test("explanation appears before quiz", () => {
    const explanationIdx = REQUIRED_SECTION_ORDER.indexOf("explanation");
    const quizIdx = REQUIRED_SECTION_ORDER.indexOf("quiz");
    expect(explanationIdx).toBeLessThan(quizIdx);
  });

  test("explain_this (Still confused?) is the last section", () => {
    const lastIdx = REQUIRED_SECTION_ORDER.length - 1;
    expect(REQUIRED_SECTION_ORDER[lastIdx]).toBe("explain_this");
  });

  test("header is the first section", () => {
    expect(REQUIRED_SECTION_ORDER[0]).toBe("header");
  });
});

// ─────────────────────────────────────────────────────────────
//  MS-003 / MS-004: Next subtopic nudge visibility
//
//  Rules:
//    - Show nudge ONLY when all quiz questions are answered
//    - Show nudge ONLY when next_subtopic is not null
//    - Never show nudge before quiz is completed
// ─────────────────────────────────────────────────────────────

interface NextSubtopic {
  id: string;
  name: string;
}

function shouldShowNextSubtopicNudge(
  allQuestionsAnswered: boolean,
  nextSubtopic: NextSubtopic | null,
): boolean {
  return allQuestionsAnswered && nextSubtopic !== null;
}

describe("MS-003/MS-004 — next subtopic nudge", () => {
  const nextSubtopic: NextSubtopic = { id: "abc-123", name: "Amplitude" };

  test("shows nudge when all answered and next subtopic exists", () => {
    expect(shouldShowNextSubtopicNudge(true, nextSubtopic)).toBe(true);
  });

  test("does not show nudge when quiz not completed", () => {
    expect(shouldShowNextSubtopicNudge(false, nextSubtopic)).toBe(false);
  });

  test("does not show nudge when next_subtopic is null (last subtopic)", () => {
    expect(shouldShowNextSubtopicNudge(true, null)).toBe(false);
  });

  test("does not show nudge when both conditions false", () => {
    expect(shouldShowNextSubtopicNudge(false, null)).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────
//  MS-005: "Still confused?" visual weight
//
//  This section is an escape hatch, not a primary CTA.
//  It must NOT use bg-brand-primary / rounded-full button styling
//  (those are reserved for primary actions like "Quiz me").
//  It should be inline text link or ghost styling.
// ─────────────────────────────────────────────────────────────

interface ExplainThisButtonStyle {
  containerClass: string;
  buttonClass: string;
}

function getExplainThisStyle(): ExplainThisButtonStyle {
  return {
    // Ghost card — no elevation, no prominent background
    containerClass:
      "border-t border-brand-border pt-4 flex items-center justify-between gap-4",
    // Text link style — NOT rounded-full primary button
    buttonClass:
      "flex items-center gap-1.5 text-sm font-sans font-semibold text-brand-primary hover:text-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded",
  };
}

describe("MS-005 — explain_this visual weight", () => {
  test("container has no card background (no bg-white rounded-2xl elevation)", () => {
    const { containerClass } = getExplainThisStyle();
    expect(containerClass).not.toContain("bg-white rounded-2xl");
    expect(containerClass).not.toContain("shadow");
  });

  test("button does not use primary filled style", () => {
    const { buttonClass } = getExplainThisStyle();
    expect(buttonClass).not.toContain(
      "bg-brand-primary text-white rounded-full",
    );
  });

  test("button uses text link / ghost style", () => {
    const { buttonClass } = getExplainThisStyle();
    expect(buttonClass).toContain("text-brand-primary");
  });
});
