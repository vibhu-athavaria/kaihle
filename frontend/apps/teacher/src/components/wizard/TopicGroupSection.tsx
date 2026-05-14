import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { TopicRow, type TopicWithAvailability } from "./TopicRow";

interface TopicGroupSectionProps {
  gradeLabel: string;
  isCurrent: boolean;
  topics: TopicWithAvailability[];
  selectedIds: Set<string>;
  questionsPerTopic: number;
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  defaultOpen?: boolean;
}

export function TopicGroupSection({
  gradeLabel,
  isCurrent,
  topics,
  selectedIds,
  questionsPerTopic,
  onToggle,
  onSelectAll,
  defaultOpen = true,
}: TopicGroupSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const selectedCount = topics.filter((t) =>
    selectedIds.has(t.curriculum_topic_id),
  ).length;

  // Current grade: gold/amber tint; previous grade: green tint
  const headerClass = isCurrent
    ? "px-[14px] py-[7px] text-[10px] font-bold uppercase tracking-[0.6px] bg-[#fffbeb] border-b border-[#fde68a] text-[#92400e]"
    : "px-[14px] py-[7px] text-[10px] font-bold uppercase tracking-[0.6px] bg-[#f0fdf4] border-b border-[#b5d4bc] text-[#1a5c38]";

  const selectAllColor = isCurrent ? "text-brand-gold" : "text-brand-primary";

  const sectionId = `topic-group-${gradeLabel.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <>
      <div
        className={`${headerClass} flex items-center justify-between cursor-pointer select-none`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={sectionId}
        role="button"
      >
        <div className="flex items-center gap-[6px] flex-1">
          {open ? (
            <ChevronDown
              className="w-3.5 h-3.5 flex-shrink-0"
              aria-hidden="true"
            />
          ) : (
            <ChevronRight
              className="w-3.5 h-3.5 flex-shrink-0"
              aria-hidden="true"
            />
          )}
          <span>{gradeLabel}</span>
          {!open && (
            <span className="text-xs font-medium normal-case tracking-normal text-brand-muted ml-1">
              {selectedCount > 0
                ? `${selectedCount} selected · click to expand`
                : "click to expand"}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSelectAll();
          }}
          className={`text-xs font-bold ${selectAllColor} hover:opacity-70 transition-opacity min-h-[44px] px-1`}
          aria-label={`Select all topics in ${gradeLabel}`}
        >
          Select all
        </button>
      </div>

      <div id={sectionId}>
        {open &&
          topics.map((topic) => (
            <TopicRow
              key={topic.curriculum_topic_id}
              topic={topic}
              selected={selectedIds.has(topic.curriculum_topic_id)}
              questionsPerTopic={questionsPerTopic}
              onToggle={() => onToggle(topic.curriculum_topic_id)}
            />
          ))}
      </div>
    </>
  );
}
