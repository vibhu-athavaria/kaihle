/**
 * Unit tests for TopicDetailPage logic.
 *
 * Tests cover:
 *   - TD-001: subtopic CTA label derives from progress status
 *   - TD-002: subtopic badge style maps to design-system colors (no gray data colors)
 */

import type { SubtopicStatus } from "../../../hooks/useTopicSubtopics";

// ─────────────────────────────────────────────────────────────
//  TD-003: card_status = "no_content" when has_content is false
//
//  Bug: subtopic cards show "Not started / Start" even when the
//  teacher has never generated content. The student clicks in
//  and sees empty states — misleading and frustrating.
//
//  Fix: extend SubtopicStatus to include "no_content" and derive
//  the displayed badge/CTA from card_status (which merges has_content
//  + progress) instead of progress.status alone.
// ─────────────────────────────────────────────────────────────

type CardStatus = SubtopicStatus | "no_content";

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

// ─────────────────────────────────────────────────────────────
//  TD-003: card_status derivation from has_content + progress
// ─────────────────────────────────────────────────────────────

function deriveCardStatus(
  hasContent: boolean,
  progressStatus: SubtopicStatus | undefined,
): CardStatus {
  if (!hasContent) return "no_content";
  return progressStatus ?? "not_started";
}

function getCardBadgeStyle(status: CardStatus): {
  containerClass: string;
  label: string;
} {
  switch (status) {
    case "no_content":
      return {
        containerClass: "bg-brand-muted/20 text-brand-muted font-medium",
        label: "Coming soon",
      };
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

function getCardCtaLabel(status: CardStatus): string {
  switch (status) {
    case "no_content":
      return "Coming soon";
    case "completed":
      return "Review";
    case "in_progress":
      return "Resume";
    default:
      return "Start";
  }
}

describe("TD-003 — card_status: no_content when teacher hasn't generated content", () => {
  test("derives no_content when has_content is false, regardless of progress", () => {
    expect(deriveCardStatus(false, "not_started")).toBe("no_content");
    expect(deriveCardStatus(false, "in_progress")).toBe("no_content");
    expect(deriveCardStatus(false, "completed")).toBe("no_content");
    expect(deriveCardStatus(false, undefined)).toBe("no_content");
  });

  test("derives progress status when has_content is true", () => {
    expect(deriveCardStatus(true, "not_started")).toBe("not_started");
    expect(deriveCardStatus(true, "in_progress")).toBe("in_progress");
    expect(deriveCardStatus(true, "completed")).toBe("completed");
  });

  test("derives not_started when has_content is true but no progress row", () => {
    expect(deriveCardStatus(true, undefined)).toBe("not_started");
  });

  test("no_content badge uses muted style — not a call-to-action color", () => {
    const { containerClass, label } = getCardBadgeStyle("no_content");
    expect(label).toBe("Coming soon");
    expect(containerClass).toContain("brand-muted");
    expect(containerClass).not.toContain("brand-primary");
    expect(containerClass).not.toContain("brand-green");
    expect(containerClass).not.toContain("brand-gold");
    expect(containerClass).not.toContain("gray-100");
  });

  test("no_content CTA says Coming soon (not Start)", () => {
    expect(getCardCtaLabel("no_content")).toBe("Coming soon");
  });

  test("Start CTA only appears when has_content is true and not started", () => {
    expect(getCardCtaLabel(deriveCardStatus(true, "not_started"))).toBe(
      "Start",
    );
    expect(getCardCtaLabel(deriveCardStatus(false, "not_started"))).not.toBe(
      "Start",
    );
  });
});
