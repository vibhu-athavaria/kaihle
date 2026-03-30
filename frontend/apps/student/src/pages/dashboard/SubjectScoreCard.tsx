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
      className={`bg-white rounded-[10px] border-[1.5px] ${borderClass} p-3 text-center`}
    >
      <div className={`text-[20px] font-bold ${textClass} mb-0.5`}>
        {displayPct}
      </div>
      <div className="text-[9px] font-bold uppercase tracking-[0.5px] text-[#9ca3af] mb-0.5">
        {subjectName}
      </div>
      <div
        className={`inline-block text-[9px] font-semibold px-1.5 py-0.5 rounded-[5px] ${textClass}`}
      >
        {label}
      </div>
    </div>
  );
}
