interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  colorClass?: string;
  size?: "sm" | "md";
}

export function ProgressBar({
  value,
  max = 100,
  label,
  colorClass = "bg-brand-primary",
  size = "sm",
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, Math.round((value / max) * 100)));
  const heightClass = size === "sm" ? "h-2" : "h-3";
  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs font-semibold text-brand-body mb-1.5">
          <span>{label}</span>
          <span>{pct}%</span>
        </div>
      )}
      <div
        className={`w-full bg-brand-border-soft rounded-full ${heightClass}`}
      >
        <div
          className={`${colorClass} ${heightClass} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
        />
      </div>
    </div>
  );
}
