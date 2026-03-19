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
      <div className={`text-2xl font-extrabold ${textClass}`}>{displayPct}</div>
      <div className="text-xs font-bold uppercase tracking-wide text-brand-muted mt-1">
        {subjectName}
      </div>
      <div className="text-xs text-brand-muted mt-0.5">{label}</div>
    </div>
  );
}
