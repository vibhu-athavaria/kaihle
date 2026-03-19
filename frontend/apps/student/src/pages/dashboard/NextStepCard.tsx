interface NextStepCardProps {
  type:
    | "assessment"
    | "study-plan-ready"
    | "study-plan-progress"
    | "weakest-area";
  title: string;
  subtitle: string;
  actionLabel: string;
  onAction?: () => void;
}

const emojiMap: Record<string, string> = {
  assessment: "📝",
  "study-plan-ready": "📚",
  "study-plan-progress": "📈",
  "weakest-area": "🎯",
};

export function NextStepCard({
  type,
  title,
  subtitle,
  actionLabel,
  onAction,
}: NextStepCardProps) {
  const emoji = emojiMap[type];

  return (
    <div className="bg-white rounded-2xl border border-role-student-border p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-2xl" role="img" aria-label={type}>
          {emoji}
        </span>
        <div>
          <div className="font-semibold text-brand-ink">{title}</div>
          <div className="text-xs text-brand-muted">{subtitle}</div>
        </div>
      </div>
      <button
        onClick={onAction}
        className="text-sm font-bold text-brand-primary whitespace-nowrap hover:underline"
      >
        {actionLabel}
      </button>
    </div>
  );
}

interface EmptyNextStepsProps {
  message?: string;
}

export function EmptyNextSteps({
  message = "You're all caught up! Check back after your next assessment.",
}: EmptyNextStepsProps) {
  return (
    <div className="bg-brand-light rounded-2xl p-4 text-center">
      <p className="text-sm text-brand-body">{message}</p>
    </div>
  );
}
