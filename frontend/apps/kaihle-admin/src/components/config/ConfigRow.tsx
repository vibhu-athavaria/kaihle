export type BadgeVariant = "green" | "amber" | "red";

interface ConfigRowProps {
  label: string;
  value?: string | number | null;
  badge?: {
    text: string;
    variant: BadgeVariant;
  };
  isLast?: boolean;
  testId?: string;
  valueClassName?: string;
}

const badgeStyles: Record<BadgeVariant, string> = {
  green: "bg-green-50 text-green-700 border border-green-200",
  amber: "bg-amber-50 text-amber-700 border border-amber-200",
  red: "bg-red-50 text-red-600 border border-red-200",
};

export function ConfigRow({
  label,
  value,
  badge,
  isLast = false,
  testId,
  valueClassName = "text-role-admin-ink",
}: ConfigRowProps) {
  const displayValue =
    value !== undefined && value !== null ? String(value) : "—";

  return (
    <div
      className={`flex items-center justify-between px-6 py-3.5 ${
        !isLast ? "border-b border-gray-50" : ""
      }`}
      data-testid={testId}
    >
      <span className="font-['Inter'] text-sm text-gray-500">{label}</span>
      <div className="flex items-center gap-3">
        <span
          className={`font-['Inter'] text-sm font-medium ${valueClassName}`}
        >
          {displayValue}
        </span>
        {badge && (
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
              badgeStyles[badge.variant]
            }`}
          >
            {badge.text}
          </span>
        )}
      </div>
    </div>
  );
}
