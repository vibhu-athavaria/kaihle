import { render } from "@testing-library/react";
import { GapMapCell } from "../components/GapMapCell";

/**
 * MLH-T6. Uncertainty is carried by BORDER STYLE, never by fading the fill —
 * DESIGN_SYSTEM §11 prohibits washed-out data visuals, and shape survives
 * colour-blindness and greyscale where a tint does not (§9.1).
 */
describe("GapMapCell confidence affordance", () => {
  const base = { studentName: "Priya", subtopicName: "Ordering decimals" };

  it("test_GapMapCell_when_confidence_low_then_dashed_border_applied", () => {
    render(<GapMapCell {...base} masteryScore={0.43} confidence={0.2} />);
    const el = document.querySelector("[data-provisional]");
    expect(el).not.toBeNull();
    expect(el?.className).toContain("border-dashed");
  });

  it("test_GapMapCell_when_confidence_high_then_transparent_border_applied", () => {
    render(<GapMapCell {...base} masteryScore={0.9} confidence={0.9} />);
    const el = document.querySelector("[aria-label]");
    expect(el?.className).toContain("border-transparent");
    expect(el?.className).not.toContain("border-dashed");
  });

  it("test_GapMapCell_when_confident_then_border_width_matches_provisional", () => {
    // Layout stability: both states carry border-2, so the grid never jitters.
    const { unmount } = render(
      <GapMapCell {...base} masteryScore={0.9} confidence={0.9} />,
    );
    expect(document.querySelector("[aria-label]")?.className).toContain(
      "border-2",
    );
    unmount();
    render(<GapMapCell {...base} masteryScore={0.9} confidence={0.1} />);
    expect(document.querySelector("[aria-label]")?.className).toContain(
      "border-2",
    );
  });

  it("test_GapMapCell_when_confidence_low_then_aria_label_says_provisional", () => {
    render(<GapMapCell {...base} masteryScore={0.43} confidence={0.2} />);
    expect(
      document.querySelector("[aria-label]")?.getAttribute("aria-label"),
    ).toContain("provisional");
  });

  it("test_GapMapCell_when_total_responses_present_then_aria_label_includes_count", () => {
    render(
      <GapMapCell
        {...base}
        masteryScore={0.43}
        confidence={0.2}
        totalResponses={2}
      />,
    );
    const label = document
      .querySelector("[aria-label]")
      ?.getAttribute("aria-label");
    expect(label).toContain("based on 2 responses");
  });

  it("test_GapMapCell_when_one_response_then_label_is_singular", () => {
    render(
      <GapMapCell
        {...base}
        masteryScore={0.43}
        confidence={0.2}
        totalResponses={1}
      />,
    );
    expect(
      document.querySelector("[aria-label]")?.getAttribute("aria-label"),
    ).toContain("based on 1 response");
  });

  it("test_GapMapCell_when_total_responses_null_then_aria_label_omits_count_clause", () => {
    // Null until MLH-T3 lands the column — never rendered as "based on null responses".
    render(
      <GapMapCell
        {...base}
        masteryScore={0.43}
        confidence={0.2}
        totalResponses={null}
      />,
    );
    const label = document
      .querySelector("[aria-label]")
      ?.getAttribute("aria-label");
    expect(label).toContain("provisional");
    expect(label).not.toContain("based on");
  });

  it("test_GapMapCell_when_confidence_undefined_then_renders_as_before", () => {
    // Backward compatibility: every existing caller passes no confidence.
    render(<GapMapCell {...base} masteryScore={0.9} />);
    const el = document.querySelector("[aria-label]");
    expect(el?.className).not.toContain("border-dashed");
    expect(el?.getAttribute("aria-label")).not.toContain("provisional");
  });

  it("test_GapMapCell_when_score_null_then_not_assessed_takes_precedence_over_provisional", () => {
    // An unassessed cell already says there is no evidence; dashing it would say it twice.
    render(<GapMapCell {...base} masteryScore={null} confidence={null} />);
    const el = document.querySelector("[aria-label]");
    expect(el?.getAttribute("aria-label")).toContain("Not assessed");
    expect(el?.className).not.toContain("border-dashed");
  });

  it("test_GapMapCell_when_provisional_then_fill_is_not_faded", () => {
    // The fill must stay fully saturated — no opacity, no gray substitution.
    render(<GapMapCell {...base} masteryScore={0.43} confidence={0.1} />);
    const className = document.querySelector("[aria-label]")?.className ?? "";
    expect(className).toContain("bg-brand-amber-light");
    expect(className).not.toMatch(/opacity-\d/);
  });
});
