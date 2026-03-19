interface StreakBadgeProps {
  days: number;
}

export function StreakBadge({ days }: StreakBadgeProps) {
  if (days <= 1) {
    return null;
  }

  return (
    <div className="inline-flex items-center gap-1.5 bg-brand-gold-light px-3 py-1.5 rounded-full">
      <span role="img" aria-label="fire">
        🔥
      </span>
      <span className="text-sm font-bold text-brand-gold-dark">
        {days} day{days !== 1 ? "s" : ""}
      </span>
    </div>
  );
}
