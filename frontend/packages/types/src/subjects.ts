export const SUBJECT_COLORS: Record<string, string> = {
  Mathematics: "bg-brand-primary",
  "Integrated Science": "bg-violet-600",
  Biology: "bg-green-600",
  Chemistry: "bg-amber-600",
  Physics: "bg-blue-600",
  "English Language": "bg-red-600",
  "English Literature": "bg-purple-600",
  default: "bg-brand-muted",
};

export function getSubjectColor(subjectName: string): string {
  return SUBJECT_COLORS[subjectName] || SUBJECT_COLORS.default;
}
