import { useState } from "react";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
import { SubtopicScoreRow } from "./SubtopicScoreRow";

interface Subtopic {
  subtopicId: string;
  subtopicName: string;
  masteryScore: number | null;
  lastAssessedAt: string | null;
}

interface TopicSectionProps {
  topicName: string;
  subtopics: Subtopic[];
  defaultExpanded?: boolean;
}

export function TopicSection({
  topicName,
  subtopics,
  defaultExpanded = false,
}: TopicSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const assessedSubtopics = subtopics.filter((s) => s.masteryScore !== null);
  const topicAvgScore =
    assessedSubtopics.length > 0
      ? assessedSubtopics.reduce((acc, s) => acc + s.masteryScore!, 0) /
        assessedSubtopics.length
      : null;

  const { dotClass, textClass, label } = getMasteryStyle(topicAvgScore);
  const displayPct = scoreToPercent(topicAvgScore);

  return (
    <div className="border border-brand-border rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-brand-surface transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${dotClass}`} />
          <span className="font-sans font-semibold text-brand-ink">
            {topicName}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className={`font-sans text-sm font-semibold ${textClass}`}>
              {displayPct}
            </span>
            <span className="font-sans text-xs text-brand-muted ml-2">
              {label}
            </span>
          </div>
          <svg
            className={`w-4 h-4 text-brand-muted transition-transform ${
              isExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-brand-border bg-brand-surface/50 p-2 space-y-1">
          {subtopics.map((subtopic) => (
            <SubtopicScoreRow
              key={subtopic.subtopicId}
              subtopicId={subtopic.subtopicId}
              subtopicName={subtopic.subtopicName}
              masteryScore={subtopic.masteryScore}
              lastAssessedAt={subtopic.lastAssessedAt}
            />
          ))}
        </div>
      )}
    </div>
  );
}
