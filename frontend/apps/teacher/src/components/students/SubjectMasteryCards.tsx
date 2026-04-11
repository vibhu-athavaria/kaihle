import { getMasteryStyle } from "@kaihle/types";

interface SubjectMasteryCard {
  subjectId: string;
  subjectName: string;
  avgMastery: number | null;
}

interface SubjectMasteryCardsProps {
  subjects: SubjectMasteryCard[];
}

export function SubjectMasteryCards({ subjects }: SubjectMasteryCardsProps) {
  if (subjects.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {subjects.map((subject) => {
        const { textClass, label } = getMasteryStyle(subject.avgMastery);
        const borderColor =
          subject.avgMastery === null
            ? "border-gray-100"
            : subject.avgMastery > 0.7
              ? "border-brand-green"
              : subject.avgMastery >= 0.4
                ? "border-brand-amber"
                : "border-brand-red";

        return (
          <div
            key={subject.subjectId}
            className={`bg-white rounded-xl border border-gray-100 border-l-4 ${borderColor} p-4`}
          >
            <div className="font-display text-sm font-semibold text-brand-ink mb-1">
              {subject.subjectName}
            </div>
            <div className={`text-2xl font-display font-bold ${textClass}`}>
              {subject.avgMastery !== null
                ? `${Math.round(subject.avgMastery * 100)}%`
                : "—"}
            </div>
            <div className="text-xs text-brand-muted mt-0.5">{label}</div>
          </div>
        );
      })}
    </div>
  );
}
