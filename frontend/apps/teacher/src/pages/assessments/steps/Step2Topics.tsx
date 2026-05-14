import { Button, Skeleton } from "@kaihle/ui";
import { useAssessmentWizard } from "../../../hooks/useAssessmentWizard";
import { useClassTopicsWithGrades } from "../../../hooks/useClassTopicsWithGrades";
import type { DiagnosticTopicItem } from "../../../hooks/useClassTopicsWithGrades";

function TopicSection({
  label,
  topics,
  topicIds,
  onToggle,
}: {
  label: string;
  topics: DiagnosticTopicItem[];
  topicIds: string[];
  onToggle: (id: string) => void;
}) {
  if (topics.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted mb-2 px-1">
        {label}
      </p>
      <div className="border border-brand-border rounded-xl divide-y divide-brand-border-soft overflow-hidden">
        {topics.map((topic) => {
          const checked = topicIds.includes(topic.curriculum_topic_id);
          return (
            <label
              key={topic.curriculum_topic_id}
              className={[
                "flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors",
                "hover:bg-brand-gold-light/30",
                checked ? "bg-brand-gold-light/20" : "bg-white",
              ].join(" ")}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(topic.curriculum_topic_id)}
                className="w-4 h-4 rounded border-brand-border text-brand-gold focus:ring-brand-gold"
                aria-label={topic.topic_name}
              />
              <span className="text-sm font-sans text-brand-ink flex-1">
                {topic.topic_name}
              </span>
              {topic.subtopic_count > 0 && (
                <span className="text-xs font-sans text-brand-muted">
                  {topic.subtopic_count} subtopic
                  {topic.subtopic_count !== 1 ? "s" : ""}
                </span>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}

export function Step2Topics() {
  const { classId, topicIds, setTopicIds, setStep } = useAssessmentWizard();

  const { data, isLoading, isError, refetch } = useClassTopicsWithGrades(
    classId ?? undefined,
  );

  const currentTopics = data?.current_grade_topics ?? [];
  const previousTopics = data?.previous_grade_topics ?? [];
  const allTopics = [...previousTopics, ...currentTopics];
  const allTopicIds = allTopics.map((t) => t.curriculum_topic_id);

  const canProceed = topicIds.length > 0;

  function toggleTopic(id: string) {
    if (topicIds.includes(id)) {
      setTopicIds(topicIds.filter((t) => t !== id));
    } else {
      setTopicIds([...topicIds, id]);
    }
  }

  function toggleAll() {
    if (topicIds.length === allTopicIds.length) {
      setTopicIds([]);
    } else {
      setTopicIds(allTopicIds);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-sans font-semibold text-brand-ink">
            Select Topics
          </p>
          {allTopics.length > 0 && (
            <button
              type="button"
              onClick={toggleAll}
              className="text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
            >
              {topicIds.length === allTopicIds.length
                ? "Deselect all"
                : "Select all"}
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : isError ? (
          <div className="border border-red-200 bg-red-50 rounded-xl p-6 text-center">
            <p className="text-sm font-sans font-semibold text-red-700 mb-1">
              Failed to load topics
            </p>
            <p className="text-xs font-sans text-brand-muted mb-3">
              Could not connect to the curriculum service. Please try again.
            </p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
            >
              Try again →
            </button>
          </div>
        ) : allTopics.length === 0 ? (
          <div className="border border-brand-border rounded-xl p-6 text-center">
            <p className="text-sm font-sans text-brand-muted">
              No topics defined for this subject and grade yet.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {previousTopics.length > 0 && (
              <TopicSection
                label={`Grade ${data!.previous_grade_level} — Prior Year`}
                topics={previousTopics}
                topicIds={topicIds}
                onToggle={toggleTopic}
              />
            )}
            <TopicSection
              label={`Grade ${data!.current_grade_level} — Current Year`}
              topics={currentTopics}
              topicIds={topicIds}
              onToggle={toggleTopic}
            />
          </div>
        )}

        {allTopics.length > 0 && !canProceed && (
          <p className="mt-2 text-xs font-sans text-brand-red">
            Please select at least one topic to proceed.
          </p>
        )}

        {topicIds.length > 0 && (
          <p className="mt-2 text-xs font-sans text-brand-muted">
            {topicIds.length} topic{topicIds.length !== 1 ? "s" : ""} selected
          </p>
        )}
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={() => setStep(1)}>
          Back
        </Button>
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          disabled={isError || (allTopics.length > 0 && !canProceed)}
          onClick={() => setStep(3)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
