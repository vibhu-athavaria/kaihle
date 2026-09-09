import { getMasteryStyle } from "@kaihle/types";

/**
 * Legend for the gap-map heatmap.
 *
 * Lives here, beside ClassGapMapTable, because the affordance and its explanation must sit
 * at the SAME layer. The table is shared, so a visual encoding added "for the teacher app"
 * ships to every consumer automatically — but a legend duplicated in app code does not.
 * That is exactly how MLH-T6 first shipped dashed provisional cells to School Admin with
 * nothing on screen explaining them.
 *
 * Any future cell encoding belongs in this component, not in an app.
 */

/** Representative scores, one per band — chosen to sit clearly inside each range. */
const LEGEND_SCORES: Array<[number | null, string]> = [
  [0.8, "Strong"],
  [0.55, "Developing"],
  [0.2, "Needs Work"],
  [null, "Not assessed"],
];

export interface GapMapLegendProps {
  /**
   * Trailing hint, e.g. "Click any cell to view that student's full learning profile".
   * Omitted where cells are not interactive.
   */
  hint?: string;
}

export function GapMapLegend({ hint }: GapMapLegendProps) {
  return (
    <div className="flex items-center justify-between flex-wrap gap-3">
      <div className="flex items-center gap-5 flex-wrap">
        {LEGEND_SCORES.map(([score, label]) => {
          const { bgClass, textClass } = getMasteryStyle(score);
          return (
            <div key={label} className="flex items-center gap-1.5">
              <span
                className={`w-4 h-4 rounded ${bgClass}`}
                aria-hidden="true"
              />
              <span className={`text-xs font-medium ${textClass}`}>
                {label}
              </span>
            </div>
          );
        })}

        {/* Uncertainty is carried by border style, never by a washed-out fill
            (DESIGN_SYSTEM §11). Shape survives greyscale printing, a projector and
            colour-blindness, where a tint would not — satisfying §9.1, colour is never
            the only signal. */}
        <div className="flex items-center gap-1.5">
          <span
            className="w-4 h-4 rounded border-2 border-dashed border-brand-muted"
            aria-hidden="true"
          />
          <span className="text-xs font-medium text-brand-body">
            Provisional — limited evidence
          </span>
        </div>
      </div>

      {hint && <p className="text-xs text-brand-muted italic">{hint}</p>}
    </div>
  );
}
