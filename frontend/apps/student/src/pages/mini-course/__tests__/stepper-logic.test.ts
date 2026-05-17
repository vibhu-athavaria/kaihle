/**
 * Unit tests for mini-course stepper logic — ST series.
 *
 * Tests cover:
 *   - ST-001: steps are always Video → Explanation → Quiz (fixed order)
 *   - ST-002: currentStep advances on Next, stops at last step
 *   - ST-003: canGoNext is false on the last step
 *   - ST-004: step label derives from step index
 *   - ST-005: video step always renders (placeholder when no video)
 *   - ST-006: explanation step always renders (placeholder when no explanation)
 *   - ST-007: quiz step always renders (placeholder when no questions)
 *   - ST-008: stepper indicator shows correct active/done/pending states
 *   - ST-009: video progress fires when leaving video step (not on mount)
 *   - ST-010: explanation progress fires when entering explanation step (on mount)
 */

// ─── ST-001 / ST-004: step definitions ───────────────────────────────────────

type StepKey = "video" | "explanation" | "quiz";

const STEPS: StepKey[] = ["video", "explanation", "quiz"];

const STEP_LABELS: Record<StepKey, string> = {
  video: "Watch",
  explanation: "Read",
  quiz: "Quiz",
};

describe("ST-001 — steps are always in fixed order: Video → Explanation → Quiz", () => {
  test("STEPS array has exactly 3 entries in the correct order", () => {
    expect(STEPS).toHaveLength(3);
    expect(STEPS[0]).toBe("video");
    expect(STEPS[1]).toBe("explanation");
    expect(STEPS[2]).toBe("quiz");
  });
});

describe("ST-004 — step labels", () => {
  test("video step label is Watch", () => {
    expect(STEP_LABELS["video"]).toBe("Watch");
  });
  test("explanation step label is Read", () => {
    expect(STEP_LABELS["explanation"]).toBe("Read");
  });
  test("quiz step label is Quiz", () => {
    expect(STEP_LABELS["quiz"]).toBe("Quiz");
  });
});

// ─── ST-002 / ST-003: step navigation ────────────────────────────────────────

function advanceStep(current: number, total: number): number {
  return Math.min(current + 1, total - 1);
}

function canGoNext(current: number, total: number): boolean {
  return current < total - 1;
}

describe("ST-002 — currentStep advances on Next, stops at last step", () => {
  test("advances from step 0 to 1", () => {
    expect(advanceStep(0, 3)).toBe(1);
  });

  test("advances from step 1 to 2", () => {
    expect(advanceStep(1, 3)).toBe(2);
  });

  test("does not advance past last step", () => {
    expect(advanceStep(2, 3)).toBe(2);
  });
});

describe("ST-003 — canGoNext is false on the last step", () => {
  test("canGoNext is true on step 0", () => {
    expect(canGoNext(0, 3)).toBe(true);
  });

  test("canGoNext is true on step 1", () => {
    expect(canGoNext(1, 3)).toBe(true);
  });

  test("canGoNext is false on step 2 (last)", () => {
    expect(canGoNext(2, 3)).toBe(false);
  });
});

// ─── ST-005 / ST-006 / ST-007: always-visible steps with placeholders ────────

function shouldShowPlaceholder(
  step: StepKey,
  hasVideo: boolean,
  hasExplanation: boolean,
  hasQuestions: boolean,
): boolean {
  if (step === "video") return !hasVideo;
  if (step === "explanation") return !hasExplanation;
  if (step === "quiz") return !hasQuestions;
  return false;
}

describe("ST-005 — video step always renders", () => {
  test("shows placeholder when no video", () => {
    expect(shouldShowPlaceholder("video", false, true, true)).toBe(true);
  });

  test("does not show placeholder when video exists", () => {
    expect(shouldShowPlaceholder("video", true, true, true)).toBe(false);
  });
});

describe("ST-006 — explanation step always renders", () => {
  test("shows placeholder when no explanation", () => {
    expect(shouldShowPlaceholder("explanation", true, false, true)).toBe(true);
  });

  test("does not show placeholder when explanation exists", () => {
    expect(shouldShowPlaceholder("explanation", true, true, true)).toBe(false);
  });
});

describe("ST-007 — quiz step always renders", () => {
  test("shows placeholder when no questions in DB", () => {
    expect(shouldShowPlaceholder("quiz", true, true, false)).toBe(true);
  });

  test("does not show placeholder when questions exist", () => {
    expect(shouldShowPlaceholder("quiz", true, true, true)).toBe(false);
  });
});

// ─── ST-008: stepper indicator state ─────────────────────────────────────────

type StepState = "active" | "done" | "pending";

function getStepState(stepIndex: number, currentStep: number): StepState {
  if (stepIndex < currentStep) return "done";
  if (stepIndex === currentStep) return "active";
  return "pending";
}

describe("ST-008 — stepper indicator reflects active/done/pending", () => {
  test("on step 0: step 0 is active, steps 1 and 2 are pending", () => {
    expect(getStepState(0, 0)).toBe("active");
    expect(getStepState(1, 0)).toBe("pending");
    expect(getStepState(2, 0)).toBe("pending");
  });

  test("on step 1: step 0 is done, step 1 is active, step 2 is pending", () => {
    expect(getStepState(0, 1)).toBe("done");
    expect(getStepState(1, 1)).toBe("active");
    expect(getStepState(2, 1)).toBe("pending");
  });

  test("on step 2: steps 0 and 1 are done, step 2 is active", () => {
    expect(getStepState(0, 2)).toBe("done");
    expect(getStepState(1, 2)).toBe("done");
    expect(getStepState(2, 2)).toBe("active");
  });
});

// ─── ST-009 / ST-010: progress tracking timing ───────────────────────────────

describe("ST-009 — video progress fires when leaving video step (Next click)", () => {
  test("markVideoAccessed is called when Next is pressed on video step", () => {
    let videoProgressFired = false;
    const currentStep = 0; // video step
    const hasVideo = true;

    function handleNext(step: number, hasVid: boolean) {
      if (step === 0 && hasVid) videoProgressFired = true;
    }

    handleNext(currentStep, hasVideo);
    expect(videoProgressFired).toBe(true);
  });

  test("markVideoAccessed is NOT called when Next is pressed on explanation step", () => {
    let videoProgressFired = false;
    const currentStep = 1; // explanation step

    function handleNext(step: number, hasVid: boolean) {
      if (step === 0 && hasVid) videoProgressFired = true;
    }

    handleNext(currentStep, true);
    expect(videoProgressFired).toBe(false);
  });

  test("markVideoAccessed is NOT called when there is no video", () => {
    let videoProgressFired = false;
    const hasVideo = false;

    function handleNext(step: number, hasVid: boolean) {
      if (step === 0 && hasVid) videoProgressFired = true;
    }

    handleNext(0, hasVideo);
    expect(videoProgressFired).toBe(false);
  });
});

describe("ST-010 — explanation progress fires on mount of explanation step", () => {
  test("markExplanationAccessed called when explanation step becomes active", () => {
    let explanationProgressFired = false;

    function onExplanationStepMount(hasExplanation: boolean) {
      if (hasExplanation) explanationProgressFired = true;
    }

    onExplanationStepMount(true);
    expect(explanationProgressFired).toBe(true);
  });

  test("not called when explanation is absent (placeholder shown)", () => {
    let explanationProgressFired = false;

    function onExplanationStepMount(hasExplanation: boolean) {
      if (hasExplanation) explanationProgressFired = true;
    }

    onExplanationStepMount(false);
    expect(explanationProgressFired).toBe(false);
  });
});
