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
  /**
   * Tailwind border colour for the band, used to draw a provisional cell's dashed
   * outline. Stays inside the band's own colour family, so uncertainty never introduces
   * a new hue — and mastery colour is still never inlined in a component.
   */
  borderClass: string;
  /** Tailwind class for text displaying the score */
  textClass: string;
  /** Tailwind class for tinted card/row background */
  bgClass: string;
  /** Human-readable label */
  label: MasteryLabel;
  /** SVG stroke colour for ScoreRing */
  strokeColour: string;
  /** SVG text fill colour for ScoreRing */
  fillColour: string;
}

/**
 * Derive Tailwind color classes from a mastery score.
 *
 * @param score - Float 0.0–1.0, or null if not yet assessed
 * @returns MasteryStyle with Tailwind classes and label
 *
 * Bands (per CONSTITUTION §10 and DESIGN_SYSTEM.md §2):
 *   > 0.7   → Strong      (dot: brand-green, text: brand-green-dark)
 *   0.4–0.7 → Developing  (dot: brand-amber, text: brand-amber-dark)
 *   < 0.4   → Needs Work  (dot: brand-red,   text: brand-red-dark)
 *   null    → Not assessed (brand-muted)
 */
export function getMasteryStyle(score: number | null): MasteryStyle {
  if (score === null) {
    return {
      dotClass: "bg-brand-muted",
      textClass: "text-brand-muted",
      bgClass: "bg-gray-50",
      borderClass: "border-brand-muted",
      label: "Not assessed",
      strokeColour: "#9ca3af",
      fillColour: "#9ca3af",
    };
  }
  if (score > 0.7) {
    return {
      dotClass: "bg-brand-green",
      textClass: "text-brand-green-dark",
      bgClass: "bg-brand-green-light",
      borderClass: "border-brand-green-dark",
      label: "Strong",
      strokeColour: "#16a34a",
      fillColour: "#15803d",
    };
  }
  if (score >= 0.4) {
    return {
      dotClass: "bg-brand-amber",
      textClass: "text-brand-amber-dark",
      bgClass: "bg-brand-amber-light",
      borderClass: "border-brand-amber-dark",
      label: "Developing",
      strokeColour: "#f59e0b",
      fillColour: "#92400e",
    };
  }
  return {
    dotClass: "bg-brand-red",
    textClass: "text-brand-red-dark",
    bgClass: "bg-brand-red-light",
    borderClass: "border-brand-red-dark",
    label: "Needs Work",
    strokeColour: "#ef4444",
    fillColour: "#b91c1c",
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

/**
 * Confidence below which a mastery score is shown as provisional.
 *
 * Mirrors PROVISIONAL_CONFIDENCE_THRESHOLD in backend/app/services/gap_service.py — the
 * two must move together, or a cell will disagree with the column count above it.
 *
 * 0.5 is the midpoint of the current confidence ramp (min(attempts / 5, 1)), i.e. fewer
 * than roughly three attempts. MLH-T3 replaces that ramp with posterior variance, at which
 * point this value should be re-derived rather than assumed to still mean the same thing.
 */
export const PROVISIONAL_CONFIDENCE_THRESHOLD = 0.5;

export interface ConfidenceStyle {
  /** True when the score rests on too little evidence to act on by itself. */
  isProvisional: boolean;
  /**
   * Border width and style. ALWAYS "border-2" — transparent when confident — so adding a
   * visible border to a provisional cell never shifts layout and the grid cannot jitter
   * between neighbouring cells.
   */
  borderStyleClass: string;
  /** Appended to tooltip and aria-label. Empty string when confident. */
  label: string;
}

/**
 * Derive the uncertainty affordance for a mastery score.
 *
 * Deliberately separate from getMasteryStyle: that maps score to colour and must keep
 * doing exactly that. Confidence is an orthogonal dimension, and conflating them would
 * mean a low-confidence Strong cell had to pick between two colours.
 *
 * Uncertainty is carried by BORDER STYLE, never by fading or desaturating the fill.
 * DESIGN_SYSTEM.md §11 prohibits washed-out data visuals, and shape survives
 * colour-blindness, greyscale printing and a projector where a tint does not — satisfying
 * §9.1 (colour is never the only signal).
 *
 * `undefined` and `null` mean different things here, and conflating them would be a bug:
 *
 *   undefined — this caller does not supply confidence at all. Renders exactly as before,
 *               so every existing call site is unaffected. Marking these provisional would
 *               turn every cell in the app dashed overnight and make the signal meaningless.
 *   null      — the backend reported a score with no confidence behind it. That IS thin
 *               evidence, and claiming confidence we do not have is the worse error, since
 *               a teacher may act on it.
 *
 * @param confidence - Float 0.0-1.0 from gap_states.confidence.
 */
export function getConfidenceStyle(
  confidence: number | null | undefined,
): ConfidenceStyle {
  if (confidence === undefined) {
    return {
      isProvisional: false,
      borderStyleClass: "border-2 border-transparent",
      label: "",
    };
  }
  if (confidence === null || confidence < PROVISIONAL_CONFIDENCE_THRESHOLD) {
    return {
      isProvisional: true,
      borderStyleClass: "border-2 border-dashed",
      label: "provisional",
    };
  }
  return {
    isProvisional: false,
    borderStyleClass: "border-2 border-transparent",
    label: "",
  };
}
