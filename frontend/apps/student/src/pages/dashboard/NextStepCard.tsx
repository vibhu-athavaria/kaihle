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
    <div className="bg-white border border-brand-border rounded-xl p-3 flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        <span
          className="text-[14px] w-[18px] text-center"
          role="img"
          aria-label={type}
        >
          {emoji}
        </span>
        <div>
          <div className="text-[11px] font-semibold text-brand-ink">
            {title}
          </div>
          <div className="text-[9px] text-brand-muted">{subtitle}</div>
        </div>
      </div>
      <button
        onClick={onAction}
        className="text-[10px] font-bold text-brand-primary whitespace-nowrap hover:underline min-h-[44px] flex items-center focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
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
    <div className="bg-brand-light rounded-xl p-4 text-center">
      <p className="text-sm text-brand-body">{message}</p>
    </div>
  );
}
