import {
  getConfidenceStyle,
  getMasteryStyle,
  scoreToPercent,
} from "@kaihle/types";

export interface GapMapCellProps {
  masteryScore: number | null;
  studentName: string;
  subtopicName: string;
  /**
   * Evidence behind masteryScore, 0.0-1.0. Omit entirely to render exactly as before —
   * `undefined` means "this caller does not supply confidence", which is distinct from
   * `null` ("the backend reported none"). See getConfidenceStyle.
   */
  confidence?: number | null;
  /**
   * Responses behind the estimate, shown in the tooltip. "Provisional" says how sure;
   * the count says why, and it is what a teacher needs to choose between reassessing and
   * intervening. Null until MLH-T3 lands the column — the clause is simply omitted.
   */
  totalResponses?: number | null;
  /** Optional student ID — rendered as data-student-id for interop with teacher app click handlers */
  studentId?: string;
  display?: "label" | "percent" | "both";
  readOnly?: boolean;
  onClick?: () => void;
}

const LABEL_SHORT: Record<string, string> = {
  Strong: "S",
  Developing: "Dev",
  "Needs Work": "NW",
  "Not assessed": "—",
};

export function GapMapCell({
  masteryScore,
  studentName,
  subtopicName,
  studentId,
  confidence,
  totalResponses,
  display = "label",
  readOnly = false,
  onClick,
}: GapMapCellProps) {
  const { bgClass, textClass, borderClass, label } =
    getMasteryStyle(masteryScore);
  const pct = scoreToPercent(masteryScore);

  // An unassessed cell already reads "Not assessed", which says there is no evidence.
  // Adding a provisional outline on top would signal the same absence twice.
  const confidenceStyle = getConfidenceStyle(
    masteryScore === null ? undefined : confidence,
  );

  // border-2 is applied in BOTH states — transparent when confident — so a dashed border
  // never changes the cell's box size and the grid cannot jitter between neighbours.
  const borderClasses = confidenceStyle.isProvisional
    ? `${confidenceStyle.borderStyleClass} ${borderClass}`
    : confidenceStyle.borderStyleClass;

  const displayValue =
    display === "label"
      ? label
      : display === "percent"
        ? pct
        : masteryScore !== null
          ? `${LABEL_SHORT[label] ?? label.slice(0, 3)} · ${pct}`
          : "—";

  // "provisional" answers how sure; the response count answers why. The count clause is
  // dropped when unavailable rather than rendered as "based on null responses".
  const evidenceSuffix = confidenceStyle.isProvisional
    ? `, ${confidenceStyle.label}${
        totalResponses !== null && totalResponses !== undefined
          ? ` — based on ${totalResponses} response${totalResponses === 1 ? "" : "s"}`
          : ""
      }`
    : "";

  const titleText = `${studentName} — ${subtopicName}: ${label}${
    masteryScore !== null ? ` (${Math.round(masteryScore * 100)}%)` : ""
  }${evidenceSuffix}`;

  if (readOnly) {
    return (
      <div
        data-provisional={confidenceStyle.isProvisional || undefined}
        className={[
          "w-12 h-12 min-h-[44px] min-w-[44px] rounded flex items-center justify-center text-xs font-semibold",
          bgClass,
          textClass,
          borderClasses,
        ].join(" ")}
        title={titleText}
        aria-label={titleText}
      >
        {displayValue}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      data-student-id={studentId}
      data-mastery-score={masteryScore}
      data-provisional={confidenceStyle.isProvisional || undefined}
      className={[
        "w-12 h-12 min-h-[44px] min-w-[44px] rounded flex items-center justify-center text-xs font-semibold transition-all",
        "hover:scale-105 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
        bgClass,
        textClass,
        borderClasses,
      ].join(" ")}
      title={titleText}
      aria-label={titleText}
    >
      {displayValue}
    </button>
  );
}
