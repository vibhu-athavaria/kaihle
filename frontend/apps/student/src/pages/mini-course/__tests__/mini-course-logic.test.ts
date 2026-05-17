/**
 * Unit tests for MiniCoursePage logic.
 *
 * Tests cover:
 *   - MC-001: explanation_accessed must be marked when the explanation content
 *             renders, NOT when the "Explain This" AI drawer is opened
 *   - MC-002: quiz state on re-entry — past score from progress should drive
 *             the initial UI state (show result, not start gate)
 *   - MC-003: subtopic completion status derivation from progress fields
 */

// ─────────────────────────────────────────────────────────────
//  MC-001: explanation_accessed tracking — wrong action bug
//
//  Bug: handleExplanationView() marks explanation_accessed=true AND opens
//  the AI drawer. The two are unrelated — opening the AI chat does not mean
//  the student read the written explanation.
//
//  Fix: explanation_accessed should be marked by a separate
//  handleExplanationMount() called when the ExplanationCard renders.
//  The "Explain This" button should ONLY open the drawer.
//
//  Test strategy: model both handlers as pure functions and assert their
//  single-responsibility behaviour.
// ─────────────────────────────────────────────────────────────

interface MarkProgressArgs {
  explanation_accessed?: boolean;
  video_accessed?: boolean;
}

/**
 * BUGGY implementation: explanation_accessed is tied to opening the drawer.
 */
function buggy_handleExplanationView(
  explanationAccessed: boolean,
  markProgress: (args: MarkProgressArgs) => void,
  setExplainOpen: (v: boolean) => void,
) {
  if (!explanationAccessed) {
    markProgress({ explanation_accessed: true }); // wrong — drawer open ≠ explanation read
  }
  setExplainOpen(true);
}

/**
 * FIXED implementation: two separate handlers with single responsibilities.
 */
function fixed_handleExplanationMount(
  explanationAccessed: boolean,
  markProgress: (args: MarkProgressArgs) => void,
) {
  if (!explanationAccessed) {
    markProgress({ explanation_accessed: true });
  }
}

function fixed_handleExplainThisOpen(setExplainOpen: (v: boolean) => void) {
  setExplainOpen(true); // only opens the drawer — no progress side-effect
}

describe("MC-001 — explanation_accessed tracking", () => {
  test("buggy: opening AI drawer marks explanation_accessed (demonstrates the bug)", () => {
    const markProgress = jest.fn();
    const setExplainOpen = jest.fn();

    // Student has NOT read the explanation yet
    buggy_handleExplanationView(false, markProgress, setExplainOpen);

    // BUG: markProgress fires just because the drawer was opened
    expect(markProgress).toHaveBeenCalledWith({ explanation_accessed: true });
    expect(setExplainOpen).toHaveBeenCalledWith(true);
  });

  test("fixed: opening AI drawer does NOT mark explanation_accessed", () => {
    const markProgress = jest.fn();
    const setExplainOpen = jest.fn();

    // Student clicks "Still confused?" — should only open the drawer
    fixed_handleExplainThisOpen(setExplainOpen);

    expect(markProgress).not.toHaveBeenCalled();
    expect(setExplainOpen).toHaveBeenCalledWith(true);
  });

  test("fixed: explanation card mounting marks explanation_accessed when not yet tracked", () => {
    const markProgress = jest.fn();

    // Explanation card renders for first time
    fixed_handleExplanationMount(false, markProgress);

    expect(markProgress).toHaveBeenCalledWith({ explanation_accessed: true });
    expect(markProgress).toHaveBeenCalledTimes(1);
  });

  test("fixed: explanation card mounting does NOT double-mark if already accessed", () => {
    const markProgress = jest.fn();

    // Student returns — already marked
    fixed_handleExplanationMount(true, markProgress);

    expect(markProgress).not.toHaveBeenCalled();
  });
});

// ─────────────────────────────────────────────────────────────
//  MC-002: quiz initial state on re-entry
//
//  Bug: quizStarted is local state — resets to false on every navigation.
//  If check_questions_score is already recorded in progress, the page
//  should initialise showing the past result, not the "Quiz me" gate.
//
//  Fix: derive initial quiz display state from progress.check_questions_score.
// ─────────────────────────────────────────────────────────────

interface CourseProgress {
  explanation_accessed: boolean;
  video_accessed: boolean;
  check_questions_score: number | null;
}

/**
 * BUGGY: always starts at the gate regardless of past score.
 */
function buggy_getInitialQuizStarted(
  _progress: CourseProgress | null,
): boolean {
  return false; // always reset
}

/**
 * FIXED: if a score exists, skip the start gate and go straight to showing results.
 */
function fixed_getInitialQuizStarted(progress: CourseProgress | null): boolean {
  return (
    progress?.check_questions_score !== null &&
    progress?.check_questions_score !== undefined
  );
}

describe("MC-002 — quiz state on re-entry", () => {
  test("buggy: always shows start gate even when score already recorded", () => {
    const progress: CourseProgress = {
      explanation_accessed: true,
      video_accessed: true,
      check_questions_score: 0.75,
    };
    expect(buggy_getInitialQuizStarted(progress)).toBe(false); // demonstrates the bug
  });

  test("fixed: shows quiz result when check_questions_score is already recorded", () => {
    const progress: CourseProgress = {
      explanation_accessed: true,
      video_accessed: true,
      check_questions_score: 0.75,
    };
    expect(fixed_getInitialQuizStarted(progress)).toBe(true);
  });

  test("fixed: shows start gate when no score recorded yet", () => {
    const progress: CourseProgress = {
      explanation_accessed: true,
      video_accessed: false,
      check_questions_score: null,
    };
    expect(fixed_getInitialQuizStarted(progress)).toBe(false);
  });

  test("fixed: shows start gate when progress is null (first visit)", () => {
    expect(fixed_getInitialQuizStarted(null)).toBe(false);
  });

  test("fixed: treats score of 0 as completed (student scored zero — still done)", () => {
    const progress: CourseProgress = {
      explanation_accessed: true,
      video_accessed: true,
      check_questions_score: 0,
    };
    expect(fixed_getInitialQuizStarted(progress)).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────
//  MC-003: subtopic completion status derivation
//
//  Given progress fields, derive one of: "not_started" | "in_progress" | "completed"
//  Rules:
//    - not_started:  no explanation_accessed AND no video_accessed AND no score
//    - in_progress:  explanation or video accessed, but check_questions_score IS NULL
//    - completed:    check_questions_score IS NOT NULL
// ─────────────────────────────────────────────────────────────

type SubtopicStatus = "not_started" | "in_progress" | "completed";

function deriveSubtopicStatus(progress: CourseProgress | null): SubtopicStatus {
  if (!progress) return "not_started";
  if (
    progress.check_questions_score !== null &&
    progress.check_questions_score !== undefined
  ) {
    return "completed";
  }
  if (progress.explanation_accessed || progress.video_accessed) {
    return "in_progress";
  }
  return "not_started";
}

describe("MC-003 — subtopic status derivation", () => {
  test("returns not_started when progress is null", () => {
    expect(deriveSubtopicStatus(null)).toBe("not_started");
  });

  test("returns not_started when no fields are accessed and no score", () => {
    expect(
      deriveSubtopicStatus({
        explanation_accessed: false,
        video_accessed: false,
        check_questions_score: null,
      }),
    ).toBe("not_started");
  });

  test("returns in_progress when explanation accessed but no quiz score", () => {
    expect(
      deriveSubtopicStatus({
        explanation_accessed: true,
        video_accessed: false,
        check_questions_score: null,
      }),
    ).toBe("in_progress");
  });

  test("returns in_progress when video accessed but no quiz score", () => {
    expect(
      deriveSubtopicStatus({
        explanation_accessed: false,
        video_accessed: true,
        check_questions_score: null,
      }),
    ).toBe("in_progress");
  });

  test("returns completed when check_questions_score is recorded (even 0)", () => {
    expect(
      deriveSubtopicStatus({
        explanation_accessed: true,
        video_accessed: true,
        check_questions_score: 0,
      }),
    ).toBe("completed");
  });

  test("returns completed when check_questions_score is a perfect 1.0", () => {
    expect(
      deriveSubtopicStatus({
        explanation_accessed: true,
        video_accessed: true,
        check_questions_score: 1.0,
      }),
    ).toBe("completed");
  });
});
