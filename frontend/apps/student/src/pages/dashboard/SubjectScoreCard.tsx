import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

interface SubjectScoreCardProps {
  subjectName: string;
  score: number | null;
}

const borderClassMap: Record<string, string> = {
  "bg-brand-green-light": "border-brand-mid",
  "bg-brand-amber-light": "border-brand-gold-mid",
  "bg-brand-red-light": "border-brand-red/30",
  "bg-gray-50": "border-brand-border",
};

export function SubjectScoreCard({
  subjectName,
  score,
}: SubjectScoreCardProps) {
  const { bgClass, textClass, label } = getMasteryStyle(score);
  const borderClass = borderClassMap[bgClass] ?? "border-brand-border";
  const displayPct = scoreToPercent(score);

  return (
    <div
      className={`bg-white rounded-card border-[1.5px] ${borderClass} py-3 px-2.5 text-center shadow-card`}
    >
      <div
        className={`font-sans font-bold text-score-value leading-none ${textClass} mb-0.5`}
      >
        {displayPct}
      </div>
      <div className="font-sans font-bold text-score-subject uppercase tracking-[0.5px] text-brand-muted mb-0.5">
        {subjectName}
      </div>
      <div className={`font-sans font-semibold text-score-band ${textClass}`}>
        {label}
      </div>
    </div>
  );
}
