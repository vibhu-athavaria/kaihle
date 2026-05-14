/**
 * TopicPerformanceBreakdown — horizontal bar chart of per-topic class performance.
 *
 * Sorted weakest-first so teacher attention lands on gaps immediately.
 * Uses getMasteryStyle for band label + bar color — never inlines mastery logic.
 * Empty: renders nothing (caller hides the section when topic_breakdown is empty).
 */
import { getMasteryStyle } from "@kaihle/types";
import type { TopicBreakdownItem } from "../../hooks/useAssessmentResults";

interface TopicPerformanceBreakdownProps {
  topics: TopicBreakdownItem[];
  isLoading?: boolean;
}

function TopicBar({ topic }: { topic: TopicBreakdownItem }) {
  const pct = Math.round(topic.avg_score * 100);
  const { label, textClass, bgClass } = getMasteryStyle(topic.avg_score);

  return (
    <div className="flex items-center gap-4">
      <span
        className="w-40 shrink-0 text-sm text-brand-ink font-medium truncate"
        title={topic.topic_name}
      >
        {topic.topic_name}
      </span>

      <div className="flex-1 min-w-0">
        <div
          className="w-full bg-brand-border-soft rounded-full h-2"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${topic.topic_name}: ${pct}%`}
        >
          <div
            className={`h-2 rounded-full transition-all duration-500 ${bgClass.replace("bg-", "bg-").includes("light") ? "bg-brand-amber" : ""}`}
            style={{
              width: `${pct}%`,
              backgroundColor: resolveBarColor(topic.avg_score),
            }}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <span className={`text-sm font-bold ${textClass}`}>{pct}%</span>
        <span className="text-xs text-brand-muted hidden sm:inline">
          {topic.correct_count}/{topic.total_count}
        </span>
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${bgClass} ${textClass} hidden sm:inline`}
        >
          {label}
        </span>
      </div>
    </div>
  );
}

/** Maps avg_score to a raw hex color for the progress bar fill.
 *  Tailwind JIT can't resolve dynamic class names at runtime, so we use inline style. */
function resolveBarColor(score: number): string {
  if (score > 0.7) return "#16a34a"; // brand-green
  if (score >= 0.4) return "#f59e0b"; // brand-amber
  return "#ef4444"; // brand-red
}

function TopicBarSkeleton() {
  return (
    <div className="flex items-center gap-4 animate-pulse">
      <div className="w-40 h-4 bg-brand-border rounded-full" />
      <div className="flex-1 h-2 bg-brand-border rounded-full" />
      <div className="w-16 h-4 bg-brand-border rounded-full" />
    </div>
  );
}

export function TopicPerformanceBreakdown({
  topics,
  isLoading = false,
}: TopicPerformanceBreakdownProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <TopicBarSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (topics.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {topics.map((topic) => (
        <TopicBar key={topic.topic_name} topic={topic} />
      ))}
    </div>
  );
}
