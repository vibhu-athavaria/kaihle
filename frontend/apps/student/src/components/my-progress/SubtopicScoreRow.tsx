import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

interface SubtopicScoreRowProps {
  subtopicName: string;
  masteryScore: number | null;
  lastAssessedAt: string | null;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "Not yet assessed";
  const date = new Date(dateString);
  return `Assessed on ${date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })}`;
}

export function SubtopicScoreRow({
  subtopicName,
  masteryScore,
  lastAssessedAt,
}: SubtopicScoreRowProps) {
  const { dotClass, textClass } = getMasteryStyle(masteryScore);
  const displayPct = scoreToPercent(masteryScore);

  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-brand-surface transition-colors">
      <div className="flex items-center gap-3">
        <div className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
        <span className="font-sans text-sm text-brand-ink">{subtopicName}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className={`font-sans text-sm font-semibold ${textClass}`}>
          {displayPct}
        </span>
        <span className="font-sans text-xs text-brand-muted w-36 text-right">
          {formatDate(lastAssessedAt)}
        </span>
      </div>
    </div>
  );
}
