import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

interface GapMapCellProps {
  masteryScore: number | null;
  studentId: string;
  studentName: string;
  subtopicName: string;
  onClick: () => void;
}

export function GapMapCell({
  masteryScore,
  studentId,
  studentName,
  subtopicName,
  onClick,
}: GapMapCellProps) {
  const { bgClass, textClass, label } = getMasteryStyle(masteryScore);
  const displayValue = scoreToPercent(masteryScore);

  return (
    <button
      type="button"
      onClick={onClick}
      data-student-id={studentId}
      data-mastery-score={masteryScore}
      className={[
        "w-12 h-12 rounded flex items-center justify-center text-xs font-semibold transition-all",
        "hover:scale-105 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1",
        bgClass,
        textClass,
      ].join(" ")}
      title={`${studentName} — ${subtopicName}: ${label}${
        masteryScore !== null ? ` (${Math.round(masteryScore * 100)}%)` : ""
      }`}
    >
      {displayValue}
    </button>
  );
}
