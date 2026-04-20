import { useNavigate } from "react-router-dom";

interface NextStepCardProps {
  type:
    | "assessment"
    | "study-plan-ready"
    | "study-plan-progress"
    | "weakest-area";
  title: string;
  subtitle: string;
  actionLabel: string;
  route: string;
  urgent?: boolean;
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
  route,
  urgent = false,
}: NextStepCardProps) {
  const navigate = useNavigate();
  const emoji = emojiMap[type];

  return (
    <div
      className={`border rounded-card px-3.5 py-2.5 flex items-center justify-between ${
        urgent
          ? "bg-red-50 border-red-200"
          : "bg-white border-role-student-border"
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="text-step-title w-4 text-center flex-shrink-0"
          role="img"
          aria-label={type}
        >
          {emoji}
        </span>
        <div>
          <div
            className={`font-sans font-semibold text-step-title ${urgent ? "text-red-800" : "text-brand-ink"}`}
          >
            {title}
          </div>
          <div className="font-sans text-step-sub text-brand-muted mt-0.5">
            {subtitle}
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => navigate(route)}
        className={`font-sans font-bold text-step-action whitespace-nowrap hover:underline min-h-[44px] flex items-center ml-3 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
          urgent ? "text-red-700" : "text-brand-primary"
        }`}
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
