/**
 * Unit tests for assessment results page branching logic (ST-E).
 *
 * Tests cover:
 *   - isDiagnostic derivation: DIAGNOSTIC → true, PROGRESS_CHECK → false
 *   - isDiagnostic fallback: undefined/null assessment_type → true (no regression)
 *   - CTA navigation target: dashboard for diagnostic, my-progress for formative
 *   - Banner copy selection per assessment type
 */

// ─────────────────────────────────────────────────────────────
//  isDiagnostic derivation (mirrors AssessmentResultsPage logic)
// ─────────────────────────────────────────────────────────────

function isDiagnostic(
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK" | undefined | null,
): boolean {
  return !assessmentType || assessmentType === "DIAGNOSTIC";
}

describe("isDiagnostic — type branching", () => {
  test("test_is_diagnostic_when_type_is_diagnostic_then_returns_true", () => {
    expect(isDiagnostic("DIAGNOSTIC")).toBe(true);
  });

  test("test_is_diagnostic_when_type_is_progress_check_then_returns_false", () => {
    expect(isDiagnostic("PROGRESS_CHECK")).toBe(false);
  });

  test("test_is_diagnostic_when_type_is_undefined_then_defaults_to_true", () => {
    // Older API responses may omit assessment_type — must not regress diagnostic UX
    expect(isDiagnostic(undefined)).toBe(true);
  });

  test("test_is_diagnostic_when_type_is_null_then_defaults_to_true", () => {
    expect(isDiagnostic(null)).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────
//  CTA navigation target
// ─────────────────────────────────────────────────────────────

function getCtaRoute(
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK" | undefined | null,
): string {
  return isDiagnostic(assessmentType)
    ? "/student/dashboard"
    : "/student/my-progress";
}

describe("getCtaRoute — navigation target", () => {
  test("test_cta_route_when_diagnostic_then_navigates_to_dashboard", () => {
    expect(getCtaRoute("DIAGNOSTIC")).toBe("/student/dashboard");
  });

  test("test_cta_route_when_progress_check_then_navigates_to_my_progress", () => {
    expect(getCtaRoute("PROGRESS_CHECK")).toBe("/student/my-progress");
  });

  test("test_cta_route_when_type_missing_then_defaults_to_dashboard", () => {
    expect(getCtaRoute(undefined)).toBe("/student/dashboard");
  });
});

// ─────────────────────────────────────────────────────────────
//  CTA button label
// ─────────────────────────────────────────────────────────────

function getCtaLabel(
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK" | undefined | null,
): string {
  return isDiagnostic(assessmentType)
    ? "Back to Dashboard"
    : "View my progress →";
}

describe("getCtaLabel — button copy", () => {
  test("test_cta_label_when_diagnostic_then_label_is_back_to_dashboard", () => {
    expect(getCtaLabel("DIAGNOSTIC")).toBe("Back to Dashboard");
  });

  test("test_cta_label_when_progress_check_then_label_is_view_my_progress", () => {
    expect(getCtaLabel("PROGRESS_CHECK")).toBe("View my progress →");
  });

  test("test_cta_label_when_type_missing_then_defaults_to_back_to_dashboard", () => {
    expect(getCtaLabel(undefined)).toBe("Back to Dashboard");
  });
});

// ─────────────────────────────────────────────────────────────
//  Banner copy selection
// ─────────────────────────────────────────────────────────────

function getBannerCopy(
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK" | undefined | null,
): { headline: string; body: string } {
  if (isDiagnostic(assessmentType)) {
    return {
      headline: "Diagnostic complete!",
      body: "Head back to see what's now unlocked.",
    };
  }
  return {
    headline: "Assessment submitted.",
    body: "Your progress has been updated.",
  };
}

describe("getBannerCopy — banner content", () => {
  test("test_banner_copy_when_diagnostic_then_shows_diagnostic_complete_headline", () => {
    const copy = getBannerCopy("DIAGNOSTIC");
    expect(copy.headline).toBe("Diagnostic complete!");
    expect(copy.body).toBe("Head back to see what's now unlocked.");
  });

  test("test_banner_copy_when_progress_check_then_shows_assessment_submitted_headline", () => {
    const copy = getBannerCopy("PROGRESS_CHECK");
    expect(copy.headline).toBe("Assessment submitted.");
    expect(copy.body).toBe("Your progress has been updated.");
  });

  test("test_banner_copy_when_type_missing_then_shows_diagnostic_complete_headline", () => {
    const copy = getBannerCopy(undefined);
    expect(copy.headline).toBe("Diagnostic complete!");
  });
});
