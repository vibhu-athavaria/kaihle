import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
import { useConceptGuideContext } from "../../context/ConceptGuideContext";

interface SubtopicScoreRowProps {
  subtopicId: string;
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
  subtopicId,
  subtopicName,
  masteryScore,
  lastAssessedAt,
}: SubtopicScoreRowProps) {
  const { openGuide } = useConceptGuideContext();
  const { dotClass, textClass } = getMasteryStyle(masteryScore);
  const displayPct = scoreToPercent(masteryScore);

  const showExplainButton = masteryScore === null || masteryScore < 0.7;

  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-brand-surface transition-colors">
      <div className="flex items-center gap-3">
        <div className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
        <span className="font-sans text-sm text-brand-ink">{subtopicName}</span>
      </div>
      <div className="flex items-center gap-4">
        {showExplainButton && (
          <button
            type="button"
            onClick={() => openGuide({ subtopicId, subtopicName, masteryScore })}
            className="font-sans text-xs text-brand-primary hover:text-brand-dark underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-1"
          >
            Explain this →
          </button>
        )}
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
