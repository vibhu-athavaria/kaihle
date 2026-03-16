/**
 * Mastery score colour band utilities.
 * Single source of truth for mastery label + Tailwind class derivation.
 *
 * Usage:
 *   import { getMasteryStyle } from '@kaihle/types'
 *   const { dotClass, textClass, bgClass, label } = getMasteryStyle(0.72)
 *   // → { dotClass: 'bg-brand-green', textClass: 'text-brand-green',
 *   //     bgClass: 'bg-brand-green-light', label: 'Strong' }
 *
 * NEVER hardcode mastery colors in components — always call this helper.
 * See docs/design/DESIGN_SYSTEM.md §2 for the full color token reference.
 */

export type MasteryLabel =
  | "Strong"
  | "Developing"
  | "Needs Work"
  | "Not assessed";

export interface MasteryStyle {
  /** Tailwind class for the colored dot/circle/cell */
  dotClass: string;
  /** Tailwind class for text displaying the score */
  textClass: string;
  /** Tailwind class for tinted card/row background */
  bgClass: string;
  /** Human-readable label */
  label: MasteryLabel;
}

/**
 * Derive Tailwind color classes from a mastery score.
 *
 * @param score - Float 0.0–1.0, or null if not yet assessed
 * @returns MasteryStyle with Tailwind classes and label
 *
 * Bands (per CONSTITUTION §10 and DESIGN_SYSTEM.md §2):
 *   > 0.7   → Strong      (#16a34a — brand-green)
 *   0.4–0.7 → Developing  (#f59e0b — brand-amber)
 *   < 0.4   → Needs Work  (#ef4444 — brand-red)
 *   null    → Not assessed (#9ca3af — brand-muted)
 */
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) {
    return {
      dotClass: "bg-brand-muted",
      textClass: "text-brand-muted",
      bgClass: "bg-gray-50",
      label: "Not assessed",
    };
  }
  if (score > 0.7) {
    return {
      dotClass: "bg-brand-green",
      textClass: "text-brand-green",
      bgClass: "bg-brand-green-light",
      label: "Strong",
    };
  }
  if (score >= 0.4) {
    return {
      dotClass: "bg-brand-amber",
      textClass: "text-brand-amber",
      bgClass: "bg-brand-amber-light",
      label: "Developing",
    };
  }
  return {
    dotClass: "bg-brand-red",
    textClass: "text-brand-red",
    bgClass: "bg-brand-red-light",
    label: "Needs Work",
  };
}

/**
 * Convert a float score (0.0–1.0) to a display percentage string.
 * Always use this — never display raw floats to users.
 *
 * @example scoreToPercent(0.72) → "72%"
 * @example scoreToPercent(null) → "—"
 */
export function scoreToPercent(score: number | null): string {
  if (score === null) return "—";
  return `${Math.round(score * 100)}%`;
}
