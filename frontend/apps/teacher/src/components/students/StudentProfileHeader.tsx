import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

interface StudentProfileHeaderProps {
  name: string;
  email?: string | null;
  className?: string | null;
  avgMastery?: number | null;
}

export function StudentProfileHeader({
  name,
  email,
  className,
  avgMastery,
}: StudentProfileHeaderProps) {
  const { textClass, dotClass, label } = getMasteryStyle(avgMastery ?? null);
  const displayPct = scoreToPercent(avgMastery ?? null);

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex items-start gap-4">
        <Link
          to="/teacher/dashboard"
          className="mt-1 inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded"
        >
          <ChevronLeft className="w-4 h-4" aria-hidden="true" />
        </Link>
        <div>
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            {name}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            {email && <span className="text-sm text-brand-muted">{email}</span>}
            {className && (
              <span className="px-2 py-0.5 bg-gray-100 text-xs font-medium text-brand-muted rounded-full">
                {className}
              </span>
            )}
          </div>
        </div>
      </div>
      {avgMastery !== undefined && avgMastery !== null && (
        <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-xl border border-brand-border shadow-sm">
          <span className={`w-3 h-3 rounded-full ${dotClass}`} />
          <span className={`text-lg font-semibold ${textClass}`}>
            {displayPct}
          </span>
          <span className="text-sm text-brand-muted">{label}</span>
        </div>
      )}
    </div>
  );
}
