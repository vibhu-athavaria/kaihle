import type { TopicAvailability } from "../../hooks/useTopicAvailability";

export interface TopicWithAvailability {
  curriculum_topic_id: string;
  topic_name: string;
  grade_level: number;
  subtopic_count: number;
  availability?: TopicAvailability;
  availabilityLoading?: boolean;
}

interface TopicRowProps {
  topic: TopicWithAvailability;
  selected: boolean;
  questionsPerTopic: number;
  onToggle: () => void;
}

export function TopicRow({
  topic,
  selected,
  questionsPerTopic,
  onToggle,
}: TopicRowProps) {
  const avail = topic.availability;
  const loading = topic.availabilityLoading;

  const isError = avail !== undefined && avail.available_questions === 0;
  const isWarn =
    avail !== undefined &&
    avail.available_questions > 0 &&
    avail.available_questions < questionsPerTopic;
  let rowClass =
    "flex items-center gap-3 px-[14px] py-3 border-b border-[#f3f4f6] last:border-b-0 cursor-pointer bg-white transition-colors";
  if (selected && isWarn)
    rowClass =
      "flex items-center gap-3 px-[14px] py-3 border-b border-[#f3f4f6] last:border-b-0 cursor-pointer bg-[#fffbeb] border-l-2 border-[#f59e0b] transition-colors";
  else if (selected && isError)
    rowClass =
      "flex items-center gap-3 px-[14px] py-3 border-b border-[#f3f4f6] last:border-b-0 cursor-pointer bg-[#fee2e2] border-l-2 border-[#ef4444] transition-colors";
  else if (!selected)
    rowClass =
      "flex items-center gap-3 px-[14px] py-3 border-b border-[#f3f4f6] last:border-b-0 cursor-pointer bg-white opacity-60 transition-colors";

  return (
    <label className={rowClass}>
      <input
        type="checkbox"
        checked={selected}
        onChange={onToggle}
        className="w-4 h-4 rounded border-[#d1d5db] accent-[#c9932a] flex-shrink-0 cursor-pointer focus-visible:ring-2 focus-visible:ring-[#c9932a]"
      />
      <div className="flex-1 min-w-0">
        <p
          className={`text-sm font-semibold truncate ${selected ? "text-[#374151]" : "text-[#9ca3af]"}`}
        >
          {topic.topic_name}
        </p>
        {selected && isWarn && (
          <p className="text-xs text-[#92400e] mt-px">
            ⚠ Only {avail!.available_questions} question
            {avail!.available_questions !== 1 ? "s" : ""} available — need{" "}
            {questionsPerTopic}
          </p>
        )}
        {selected && isError && (
          <p className="text-xs text-[#ef4444] mt-px">
            ✕ No questions in bank for this topic
          </p>
        )}
      </div>

      {/* Availability indicator — only shown when there's a problem */}
      {loading && selected && (
        <div className="w-12 h-5 rounded-full bg-gray-100 animate-pulse flex-shrink-0" />
      )}
    </label>
  );
}
