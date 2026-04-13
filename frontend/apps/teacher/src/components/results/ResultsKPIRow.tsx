/**
 * ResultsKPIRow — 4-card KPI summary row for assessment results.
 *
 * Cards: Submitted, Class avg, Highest scorer, Needs attention.
 * Loading: 4 skeleton cards (never shows "0 of 0").
 * Empty: dedicated "No submissions yet" text instead of zeros.
 */
import React from "react";
import { getMasteryStyle } from "@kaihle/types";
import type { StudentAttemptSummary } from "../../hooks/useAssessmentResults";

interface ResultsKPIRowProps {
  isLoading: boolean;
  totalStudents: number;
  attempts: StudentAttemptSummary[];
}

interface KPICardProps {
  label: string;
  children: React.ReactNode;
  ariaLabel: string;
}

function KPICard({ label, children, ariaLabel }: KPICardProps) {
  return (
    <div
      className="bg-white rounded-2xl border border-brand-border shadow-sm p-5"
      aria-label={ariaLabel}
    >
      <div className="font-sans text-[11px] uppercase tracking-[0.08em] text-brand-muted mb-1">
        {label}
      </div>
      {children}
    </div>
  );
}

function KPICardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border shadow-sm p-5 animate-pulse">
      <div className="h-3 w-20 bg-gray-100 rounded mb-2" />
      <div className="h-8 w-28 bg-gray-100 rounded" />
      <div className="h-3 w-16 bg-gray-100 rounded mt-2" />
    </div>
  );
}

export function ResultsKPIRow({
  isLoading,
  totalStudents,
  attempts,
}: ResultsKPIRowProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <KPICardSkeleton key={i} />
        ))}
      </div>
    );
  }

  const submitted = attempts.filter((a) => a.status === "SUBMITTED");
  const submittedCount = submitted.length;

  // Class average
  const scores = submitted
    .map((a) => a.score)
    .filter((s): s is number => s !== null);
  const avgScore =
    scores.length > 0
      ? scores.reduce((a, b) => a + b, 0) / scores.length
      : null;
  const avgStyle = getMasteryStyle(avgScore);

  // Highest scorer
  const highest =
    scores.length > 0
      ? submitted.reduce((best, a) =>
          (a.score ?? -1) > (best.score ?? -1) ? a : best,
        )
      : null;
  const highestStyle = getMasteryStyle(highest?.score ?? null);

  // Needs attention — score < 0.4
  const needsAttentionCount = submitted.filter(
    (a) => a.score !== null && a.score < 0.4,
  ).length;

  if (submittedCount === 0) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Submitted"
          ariaLabel={`Submitted: 0 of ${totalStudents} students`}
        >
          <div className="font-display text-[1.75rem] leading-none text-brand-ink">
            0
          </div>
          <div className="text-xs text-brand-muted mt-1">
            of {totalStudents}
          </div>
        </KPICard>
        <KPICard
          label="Class avg"
          ariaLabel="Class average: no submissions yet"
        >
          <div className="font-display text-[1.75rem] leading-none text-brand-muted">
            —
          </div>
          <div className="text-xs text-brand-muted mt-1">
            No students have submitted yet
          </div>
        </KPICard>
        <KPICard label="Highest" ariaLabel="Highest: no submissions yet">
          <div className="font-display text-[1.75rem] leading-none text-brand-muted">
            —
          </div>
        </KPICard>
        <KPICard
          label="Needs attention"
          ariaLabel="Needs attention: no submissions yet"
        >
          <div className="font-display text-[1.75rem] leading-none text-brand-muted">
            0
          </div>
          <div className="text-xs text-brand-muted mt-1">scoring below 40%</div>
        </KPICard>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {/* Submitted */}
      <KPICard
        label="Submitted"
        ariaLabel={`Submitted: ${submittedCount} of ${totalStudents}`}
      >
        <div className="font-display text-[1.75rem] leading-none text-brand-ink">
          {submittedCount} of {totalStudents}
        </div>
      </KPICard>

      {/* Class avg */}
      <KPICard
        label="Class avg"
        ariaLabel={`Class average: ${
          avgScore !== null ? Math.round(avgScore * 100) : 0
        }%, ${avgStyle.label}`}
      >
        <div
          className={`font-display text-[1.75rem] leading-none ${avgStyle.textClass}`}
        >
          {avgScore !== null ? `${Math.round(avgScore * 100)}%` : "—"}
        </div>
        <div className={`text-xs mt-1 ${avgStyle.textClass}`}>
          {avgStyle.label}
        </div>
      </KPICard>

      {/* Highest */}
      <KPICard
        label="Highest"
        ariaLabel={`Highest: ${highest?.studentName ?? "—"}, ${
          highest?.score !== null && highest?.score !== undefined
            ? Math.round(highest.score * 100)
            : 0
        }%, ${highestStyle.label}`}
      >
        <div className="font-display text-[1.75rem] leading-none text-brand-ink truncate">
          {highest?.studentName ?? "—"}
        </div>
        {highest && (
          <div className={`text-xs mt-1 ${highestStyle.textClass}`}>
            {highest.score !== null && highest.score !== undefined
              ? `${Math.round(highest.score * 100)}% · ${highestStyle.label}`
              : "—"}
          </div>
        )}
      </KPICard>

      {/* Needs attention */}
      <KPICard
        label="Needs attention"
        ariaLabel={`Needs attention: ${needsAttentionCount} students scoring below 40%`}
      >
        <div
          className={`font-display text-[1.75rem] leading-none ${
            needsAttentionCount > 0 ? "text-brand-red" : "text-brand-muted"
          }`}
        >
          {needsAttentionCount}
        </div>
        <div className="text-xs text-brand-muted mt-1">scoring below 40%</div>
      </KPICard>
    </div>
  );
}
