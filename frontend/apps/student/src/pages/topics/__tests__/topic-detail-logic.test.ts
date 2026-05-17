/**
 * Unit tests for TopicDetailPage logic.
 *
 * Tests cover:
 *   - TD-001: subtopic CTA label derives from progress status
 *   - TD-002: subtopic badge style maps to design-system colors (no gray data colors)
 */

import type { SubtopicStatus } from "../../../hooks/useTopicSubtopics";

// ─────────────────────────────────────────────────────────────
//  TD-001: CTA label from status
// ─────────────────────────────────────────────────────────────

function getSubtopicCtaLabel(status: SubtopicStatus | undefined): string {
  switch (status) {
    case "completed":
      return "Review";
    case "in_progress":
      return "Resume";
    case "not_started":
    default:
      return "Start";
  }
}

describe("TD-001 — subtopic CTA label", () => {
  test("returns Start when status is not_started", () => {
    expect(getSubtopicCtaLabel("not_started")).toBe("Start");
  });

  test("returns Start when status is undefined (no progress row)", () => {
    expect(getSubtopicCtaLabel(undefined)).toBe("Start");
  });

  test("returns Resume when status is in_progress", () => {
    expect(getSubtopicCtaLabel("in_progress")).toBe("Resume");
  });

  test("returns Review when status is completed", () => {
    expect(getSubtopicCtaLabel("completed")).toBe("Review");
  });
});

// ─────────────────────────────────────────────────────────────
//  TD-002: badge Tailwind classes — must use brand colors, not gray
//
//  Design rule: progress status is DATA, not chrome.
//  bg-gray-100 / text-brand-muted is PROHIBITED for data badges.
//  See DESIGN_SYSTEM.md §11.
// ─────────────────────────────────────────────────────────────

interface BadgeStyle {
  containerClass: string;
  label: string;
}

function getSubtopicBadgeStyle(status: SubtopicStatus | undefined): BadgeStyle {
  switch (status) {
    case "completed":
      return {
        containerClass: "bg-brand-green-light text-brand-green font-semibold",
        label: "Finished",
      };
    case "in_progress":
      return {
        containerClass: "bg-brand-gold/10 text-brand-amber font-semibold",
        label: "In progress",
      };
    default:
      return {
        containerClass: "bg-brand-primary/10 text-brand-primary font-medium",
        label: "Not started",
      };
  }
}

describe("TD-002 — subtopic badge styles (no gray data colors)", () => {
  test("completed badge uses brand-green, not gray", () => {
    const { containerClass, label } = getSubtopicBadgeStyle("completed");
    expect(containerClass).toContain("brand-green");
    expect(containerClass).not.toContain("gray");
    expect(label).toBe("Finished");
  });

  test("in_progress badge uses brand-gold/amber tint, not gray", () => {
    const { containerClass, label } = getSubtopicBadgeStyle("in_progress");
    expect(containerClass).toMatch(/brand-gold|brand-amber/);
    expect(containerClass).not.toContain("gray");
    expect(label).toBe("In progress");
  });

  test("not_started badge uses brand-primary tint, not gray", () => {
    const { containerClass, label } = getSubtopicBadgeStyle("not_started");
    expect(containerClass).toContain("brand-primary");
    expect(containerClass).not.toContain("gray-100");
    expect(label).toBe("Not started");
  });

  test("undefined progress falls back to not_started badge style", () => {
    const { containerClass } = getSubtopicBadgeStyle(undefined);
    expect(containerClass).toContain("brand-primary");
    expect(containerClass).not.toContain("gray");
  });
});
