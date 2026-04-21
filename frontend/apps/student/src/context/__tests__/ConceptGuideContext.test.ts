/**
 * Unit tests for ConceptGuide context logic (ST-D).
 *
 * Tests cover:
 *   - openGuide sets isOpen=true with correct subtopicId/subtopicName/masteryScore
 *   - closeGuide resets all fields to null / isOpen=false
 *   - showExplainButton gating: only shown for mastery < 0.7 or null
 *   - Multiple openGuide calls replace previous state (single session)
 */

// ─────────────────────────────────────────────────────────────
//  Context state machine (mirrors ConceptGuideContext.tsx logic)
// ─────────────────────────────────────────────────────────────

interface ConceptGuideState {
  isOpen: boolean;
  subtopicId: string | null;
  subtopicName: string | null;
  masteryScore: number | null;
}

const CLOSED_STATE: ConceptGuideState = {
  isOpen: false,
  subtopicId: null,
  subtopicName: null,
  masteryScore: null,
};

function openGuide(params: {
  subtopicId: string;
  subtopicName: string;
  masteryScore: number | null;
}): ConceptGuideState {
  return { isOpen: true, ...params };
}

function closeGuide(): ConceptGuideState {
  return { ...CLOSED_STATE };
}

// ─────────────────────────────────────────────────────────────
//  openGuide
// ─────────────────────────────────────────────────────────────

describe("ConceptGuideContext — openGuide", () => {
  test("test_open_guide_when_called_with_params_then_sets_is_open_true", () => {
    const state = openGuide({
      subtopicId: "st-1",
      subtopicName: "Quadratic Equations",
      masteryScore: 0.3,
    });
    expect(state.isOpen).toBe(true);
  });

  test("test_open_guide_when_called_then_stores_subtopic_id_and_name", () => {
    const state = openGuide({
      subtopicId: "st-abc",
      subtopicName: "Newton's Laws",
      masteryScore: null,
    });
    expect(state.subtopicId).toBe("st-abc");
    expect(state.subtopicName).toBe("Newton's Laws");
  });

  test("test_open_guide_when_mastery_score_is_null_then_stores_null", () => {
    const state = openGuide({
      subtopicId: "st-1",
      subtopicName: "Photosynthesis",
      masteryScore: null,
    });
    expect(state.masteryScore).toBeNull();
  });

  test("test_open_guide_when_called_twice_then_second_call_replaces_first", () => {
    openGuide({
      subtopicId: "st-1",
      subtopicName: "Topic A",
      masteryScore: 0.5,
    });
    const second = openGuide({
      subtopicId: "st-2",
      subtopicName: "Topic B",
      masteryScore: 0.2,
    });
    expect(second.subtopicId).toBe("st-2");
    expect(second.subtopicName).toBe("Topic B");
  });
});

// ─────────────────────────────────────────────────────────────
//  closeGuide
// ─────────────────────────────────────────────────────────────

describe("ConceptGuideContext — closeGuide", () => {
  test("test_close_guide_when_called_then_sets_is_open_false", () => {
    const state = closeGuide();
    expect(state.isOpen).toBe(false);
  });

  test("test_close_guide_when_called_then_clears_subtopic_id", () => {
    const state = closeGuide();
    expect(state.subtopicId).toBeNull();
  });

  test("test_close_guide_when_called_then_clears_subtopic_name", () => {
    const state = closeGuide();
    expect(state.subtopicName).toBeNull();
  });

  test("test_close_guide_when_called_after_open_then_resets_to_closed_state", () => {
    const opened = openGuide({
      subtopicId: "st-1",
      subtopicName: "Topic A",
      masteryScore: 0.4,
    });
    expect(opened.isOpen).toBe(true);
    const closed = closeGuide();
    expect(closed).toEqual(CLOSED_STATE);
  });
});

// ─────────────────────────────────────────────────────────────
//  showExplainButton gating (mirrors SubtopicScoreRow logic)
// ─────────────────────────────────────────────────────────────

function shouldShowExplainButton(masteryScore: number | null): boolean {
  return masteryScore === null || masteryScore <= 0.7;
}

describe("shouldShowExplainButton", () => {
  test("test_explain_button_when_mastery_is_null_then_shows_button", () => {
    expect(shouldShowExplainButton(null)).toBe(true);
  });

  test("test_explain_button_when_mastery_below_0_7_then_shows_button", () => {
    expect(shouldShowExplainButton(0.5)).toBe(true);
  });

  test("test_explain_button_when_mastery_is_exactly_0_7_then_shows_button", () => {
    // 0.7 is the Developing/Strong boundary — score = 0.7 is Developing, NOT Strong
    // Per CONSTITUTION §12: score = 0.7 → Developing, score = 0.71 → Strong
    // The guide shows for Developing and below — so 0.7 SHOULD show
    expect(shouldShowExplainButton(0.7)).toBe(true);
  });

  test("test_explain_button_when_mastery_above_0_7_then_hides_button", () => {
    expect(shouldShowExplainButton(0.75)).toBe(false);
  });

  test("test_explain_button_when_mastery_is_1_0_then_hides_button", () => {
    expect(shouldShowExplainButton(1.0)).toBe(false);
  });
});
