// frontend/apps/student/src/pages/dashboard/ActionQueue.tsx
import { Link } from "react-router-dom";
import type { ActionItem } from "../../hooks/useStudentDashboard";

interface ActionQueueProps {
  items: ActionItem[];
}

const ACTION_CONFIG: Record<
  ActionItem["type"],
  { emoji: string; bgClass: string; defaultLabel: string }
> = {
  assessment_due: {
    emoji: "📋",
    bgClass: "bg-red-50",
    defaultLabel: "Assessment due",
  },
  lesson_pack_ready: {
    emoji: "📦",
    bgClass: "bg-[#f0fdf4]",
    defaultLabel: "Lesson pack ready",
  },
  study_plan_continue: {
    emoji: "📖",
    bgClass: "bg-blue-50",
    defaultLabel: "Continue study plan",
  },
  diagnostic_pending: {
    emoji: "🎯",
    bgClass: "bg-[#f0fdf4]",
    defaultLabel: "Take your diagnostic",
  },
};

function DueDateChip({
  dueDateIso,
  priority,
}: {
  dueDateIso: string | null;
  priority: number;
}): React.ReactElement | null {
  if (!dueDateIso) return null;
  const due = new Date(dueDateIso);
  const diffDays = Math.floor((due.getTime() - Date.now()) / 86_400_000);
  const label =
    diffDays <= 0
      ? "Due today"
      : diffDays === 1
        ? "Due tomorrow"
        : `Due ${due.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
  const colorClass =
    priority === 1 ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800";
  return (
    <span
      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${colorClass}`}
    >
      {label}
    </span>
  );
}

export function ActionQueue({ items }: ActionQueueProps) {
  if (items.length === 0) {
    return (
      <div
        role="status"
        className="bg-white border border-[#e5e7eb] rounded-xl px-4 py-5 text-center"
      >
        <p className="text-sm text-[#4a5240] font-semibold">
          You're all caught up!
        </p>
        <p className="text-xs text-[#9ca3af] mt-1">
          Check back after your next lesson.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#e5e7eb] rounded-xl overflow-hidden">
      {items.map((item, idx) => {
        const config = ACTION_CONFIG[item.type];
        return (
          <div
            key={`${item.type}-${item.class_id}-${idx}`}
            className="flex items-center gap-3 px-4 py-3 border-b border-gray-50 last:border-b-0"
          >
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center text-base flex-shrink-0 ${config.bgClass}`}
            >
              {config.emoji}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-[#1a2016] truncate">
                {config.defaultLabel}
              </div>
              <div className="text-[11px] text-[#9ca3af] mt-0.5">
                {item.class_name} · {item.subject_name}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <DueDateChip
                dueDateIso={item.due_date}
                priority={item.priority}
              />
              <Link
                to={item.action_url}
                className="text-[11px] font-bold px-3 py-1.5 rounded-full bg-[#1a5c38] text-white hover:opacity-90 transition-opacity"
              >
                Go →
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}
