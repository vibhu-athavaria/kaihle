import {
  getConfidenceStyle,
  getMasteryStyle,
  PROVISIONAL_CONFIDENCE_THRESHOLD,
  scoreToPercent,
} from "../mastery";

describe("getMasteryStyle", () => {
  test("score 0.85 → Strong + brand-green classes", () => {
    const s = getMasteryStyle(0.85);
    expect(s.label).toBe("Strong");
    expect(s.dotClass).toBe("bg-brand-green");
    // -dark is deliberate: brand-green on brand-green-light fails contrast, so text uses
    // the darker token (4.9:1). This expectation was stale on main and failing before T6.
    expect(s.textClass).toBe("text-brand-green-dark");
  });
  test("score 0.7 → Developing (boundary — not > 0.7)", () => {
    expect(getMasteryStyle(0.7).label).toBe("Developing");
  });
  test("score 0.71 → Strong (just over boundary)", () => {
    expect(getMasteryStyle(0.71).label).toBe("Strong");
  });
  test("score 0.4 → Developing (lower boundary — >= 0.4)", () => {
    expect(getMasteryStyle(0.4).label).toBe("Developing");
  });
  test("score 0.39 → Needs Work", () => {
    expect(getMasteryStyle(0.39).label).toBe("Needs Work");
    expect(getMasteryStyle(0.39).dotClass).toBe("bg-brand-red");
  });
  test("score null → Not assessed + muted classes", () => {
    const s = getMasteryStyle(null);
    expect(s.label).toBe("Not assessed");
    expect(s.dotClass).toBe("bg-brand-muted");
  });
});

describe("scoreToPercent", () => {
  test('0.72 → "72%"', () => expect(scoreToPercent(0.72)).toBe("72%"));
  test('0.0 → "0%"', () => expect(scoreToPercent(0.0)).toBe("0%"));
  test('1.0 → "100%"', () => expect(scoreToPercent(1.0)).toBe("100%"));
  test('null → "—"', () => expect(scoreToPercent(null)).toBe("—"));
  test('rounds correctly: 0.676 → "68%"', () =>
    expect(scoreToPercent(0.676)).toBe("68%"));
});

describe("getConfidenceStyle (MLH-T6)", () => {
  it("test_getConfidenceStyle_when_confidence_undefined_then_not_provisional", () => {
    // undefined means "this caller does not supply confidence". Treating it as provisional
    // would turn every existing cell in the app dashed and make the signal meaningless.
    expect(getConfidenceStyle(undefined).isProvisional).toBe(false);
  });

  it("test_getConfidenceStyle_when_confidence_null_then_provisional_is_true", () => {
    // null is different: the backend reported a score with no evidence behind it.
    expect(getConfidenceStyle(null).isProvisional).toBe(true);
  });

  it("test_getConfidenceStyle_when_confidence_below_threshold_then_provisional_is_true", () => {
    expect(getConfidenceStyle(0.2).isProvisional).toBe(true);
    expect(getConfidenceStyle(0.49).isProvisional).toBe(true);
  });

  it("test_getConfidenceStyle_when_threshold_compared_to_writer_ceiling_then_confident_is_reachable", () => {
    // The backend writer path caps confidence at 0.6: rolling_attempt_count is capped at 3
    // (gap_service history query uses LIMIT 2) and confidence = min(count / 5, 1). If the
    // threshold ever meets or exceeds that ceiling, NO cell can ever render confident and
    // the whole gap map goes dashed — the exact failure this affordance exists to avoid.
    // Re-derive this when MLH-T3 replaces the ramp with posterior variance.
    const WRITER_PATH_CONFIDENCE_CEILING = 0.6;
    expect(PROVISIONAL_CONFIDENCE_THRESHOLD).toBeLessThan(
      WRITER_PATH_CONFIDENCE_CEILING,
    );
    expect(
      getConfidenceStyle(WRITER_PATH_CONFIDENCE_CEILING).isProvisional,
    ).toBe(false);
  });

  it("test_getConfidenceStyle_when_confidence_at_threshold_then_provisional_is_false", () => {
    expect(
      getConfidenceStyle(PROVISIONAL_CONFIDENCE_THRESHOLD).isProvisional,
    ).toBe(false);
  });

  it("test_getConfidenceStyle_when_confidence_above_threshold_then_provisional_is_false", () => {
    expect(getConfidenceStyle(0.9).isProvisional).toBe(false);
  });

  it("test_getConfidenceStyle_when_confident_then_border_is_transparent_not_absent", () => {
    // Layout stability: border-2 is present in BOTH states, so adding a visible border to
    // a provisional cell never shifts content and the grid cannot jitter.
    const style = getConfidenceStyle(0.9);
    expect(style.borderStyleClass).toContain("border-2");
    expect(style.borderStyleClass).toContain("border-transparent");
  });

  it("test_getConfidenceStyle_when_provisional_then_border_is_dashed_same_width", () => {
    const style = getConfidenceStyle(0.1);
    expect(style.borderStyleClass).toContain("border-2");
    expect(style.borderStyleClass).toContain("border-dashed");
  });

  it("test_getConfidenceStyle_when_provisional_then_label_is_populated", () => {
    expect(getConfidenceStyle(0.1).label).toBe("provisional");
    expect(getConfidenceStyle(0.9).label).toBe("");
  });

  it("test_getConfidenceStyle_when_any_state_then_never_fades_the_fill", () => {
    // DESIGN_SYSTEM §11 prohibits washed-out data visuals. Uncertainty is carried by
    // border style only — no opacity, no gray, no saturation change.
    for (const c of [null, 0, 0.3, 0.5, 1]) {
      const style = getConfidenceStyle(c);
      expect(style.borderStyleClass).not.toMatch(/opacity|gray|grey/);
    }
  });
});

describe("getMasteryStyle borderClass (MLH-T6)", () => {
  it("test_getMasteryStyle_when_any_band_then_borderClass_is_returned", () => {
    for (const score of [null, 0.1, 0.5, 0.9]) {
      expect(getMasteryStyle(score).borderClass).toMatch(/^border-/);
    }
  });

  it("test_getMasteryStyle_when_band_has_border_then_it_stays_in_the_band_family", () => {
    // Uncertainty must never introduce a new hue.
    expect(getMasteryStyle(0.9).borderClass).toContain("green");
    expect(getMasteryStyle(0.5).borderClass).toContain("amber");
    expect(getMasteryStyle(0.1).borderClass).toContain("red");
  });

  it("test_getMasteryStyle_when_score_bands_unchanged_then_existing_classes_identical", () => {
    // T6 is additive. The display bands are explicitly out of scope.
    expect(getMasteryStyle(0.71).label).toBe("Strong");
    expect(getMasteryStyle(0.7).label).toBe("Developing");
    expect(getMasteryStyle(0.4).label).toBe("Developing");
    expect(getMasteryStyle(0.39).label).toBe("Needs Work");
    expect(getMasteryStyle(null).label).toBe("Not assessed");
    expect(getMasteryStyle(0.9).bgClass).toBe("bg-brand-green-light");
  });
});
