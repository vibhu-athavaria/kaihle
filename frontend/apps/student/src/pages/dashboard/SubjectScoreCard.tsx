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
      className={`bg-white rounded-2xl border-[1.5px] ${borderClass} p-4 text-center`}
    >
      <div
        className={`font-sans font-extrabold text-2xl leading-tight ${textClass}`}
      >
        {displayPct}
      </div>
      <div className="font-sans font-bold text-xs uppercase tracking-wide text-brand-body mt-1">
        {subjectName}
      </div>
      <div className={`font-sans text-xs text-brand-muted mt-0.5`}>{label}</div>
    </div>
  );
}
