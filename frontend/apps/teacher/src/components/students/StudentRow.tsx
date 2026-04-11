import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
import { LearningStyleTag } from "./LearningStyleTag";

interface StudentRow {
  id: string;
  name: string;
  email: string;
  avgMastery: number | null;
  lastAssessedAt: string | null;
  dominantModality: string | null;
}

interface StudentRowProps {
  student: StudentRow;
  onClick: () => void;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function StudentRow({ student, onClick }: StudentRowProps) {
  const { dotClass, textClass, label } = getMasteryStyle(student.avgMastery);
  const displayPct = scoreToPercent(student.avgMastery);

  return (
    <tr
      onClick={onClick}
      className="group cursor-pointer hover:bg-brand-bg transition-colors"
    >
      <td className="px-4 py-3 border-b border-brand-border">
        <div className="font-medium text-brand-ink group-hover:text-brand-primary transition-colors">
          {student.name || "Unknown Student"}
        </div>
        <div className="text-xs text-brand-muted">{student.email}</div>
      </td>
      <td className="px-4 py-3 border-b border-brand-border">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
          <span className={`text-sm font-semibold ${textClass}`}>
            {displayPct}
          </span>
          <span className="text-xs text-brand-muted">{label}</span>
        </div>
      </td>
      <td className="px-4 py-3 border-b border-brand-border">
        <LearningStyleTag modality={student.dominantModality} />
      </td>
      <td className="px-4 py-3 border-b border-brand-border">
        <span className="text-sm text-brand-muted">
          {formatDate(student.lastAssessedAt)}
        </span>
      </td>
    </tr>
  );
}
