import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

export interface GapMapCellProps {
  masteryScore: number | null;
  studentName: string;
  subtopicName: string;
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
  display = "percent",
  readOnly = false,
  onClick,
}: GapMapCellProps) {
  const { bgClass, textClass, label } = getMasteryStyle(masteryScore);
  const pct = scoreToPercent(masteryScore);

  const displayValue =
    display === "label"
      ? label
      : display === "percent"
        ? pct
        : masteryScore !== null
          ? `${LABEL_SHORT[label] ?? label.slice(0, 3)} · ${pct}`
          : "—";

  const titleText = `${studentName} — ${subtopicName}: ${label}${
    masteryScore !== null ? ` (${Math.round(masteryScore * 100)}%)` : ""
  }`;

  if (readOnly) {
    return (
      <div
        className={[
          "w-12 h-12 min-h-[44px] min-w-[44px] rounded flex items-center justify-center text-xs font-semibold",
          bgClass,
          textClass,
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
      className={[
        "w-12 h-12 min-h-[44px] min-w-[44px] rounded flex items-center justify-center text-xs font-semibold transition-all",
        "hover:scale-105 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
        bgClass,
        textClass,
      ].join(" ")}
      title={titleText}
      aria-label={titleText}
    >
      {displayValue}
    </button>
  );
}
