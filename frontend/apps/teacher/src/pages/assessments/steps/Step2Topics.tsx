import { Button, Skeleton } from "@kaihle/ui";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useAssessmentWizard } from "../../../hooks/useAssessmentWizard";
import type { AssessmentType } from "../../../hooks/useAssessmentWizard";
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

/**
 * Which topics arrive pre-ticked, by assessment type.
 *
 * DIAGNOSTIC and FINAL used to skip this step entirely and send no topics at all,
 * which wrote zero assessment_topic_config rows and silently degraded attempt
 * attribution. They now arrive with a sensible default the teacher can adjust.
 *
 *  - FINAL       current grade only. An end-of-term paper assesses this year's
 *                work; prior-year topics are opt-in, not the default.
 *  - DIAGNOSTIC  current + prior grade. Placement depends on finding prerequisite
 *                gaps, which usually sit in the previous year.
 *  - others      nothing pre-selected; the teacher is choosing deliberately.
 */
type PreselectMode = "current" | "all" | "none";

const PRESELECT_BY_TYPE: Record<AssessmentType, PreselectMode> = {
  FINAL: "current",
  DIAGNOSTIC: "all",
  TOPIC_SPECIFIC: "none",
  PROGRESS_CHECK: "none",
};

export function Step2Topics() {
  const { classId, assessmentType, topicIds, setTopicIds, setStep } =
    useAssessmentWizard();

  const { data, isLoading, isError, refetch } = useClassTopicsWithGrades(
    classId ?? undefined,
  );

  const currentTopics = data?.current_grade_topics ?? [];
  const previousTopics = data?.previous_grade_topics ?? [];
  const allTopics = [...previousTopics, ...currentTopics];
  const allTopicIds = allTopics.map((t) => t.curriculum_topic_id);

  // Run once per visit, after topics load. The ref stops a re-render from
  // re-ticking topics the teacher has just deselected.
  const hasPreselected = useRef(false);
  const preselectMode = assessmentType
    ? PRESELECT_BY_TYPE[assessmentType]
    : "none";

  useEffect(() => {
    if (hasPreselected.current || isLoading || allTopics.length === 0) return;
    hasPreselected.current = true;

    // Returning to this step with an existing selection must not clobber it.
    if (topicIds.length > 0 || preselectMode === "none") return;

    setTopicIds(
      preselectMode === "current"
        ? currentTopics.map((t) => t.curriculum_topic_id)
        : allTopicIds,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, data, preselectMode]);

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
            <p className="text-sm font-sans font-semibold text-brand-ink mb-1">
              No topics available
            </p>
            <p className="text-xs font-sans text-brand-muted max-w-sm mx-auto">
              This class&apos;s subject and grade have no curriculum topics yet,
              so an assessment cannot be created. Ask your school admin to set
              up the curriculum for this class.
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

        {allTopics.length > 0 && preselectMode !== "none" && (
          <p className="mt-2 text-xs font-sans text-brand-muted italic">
            {preselectMode === "current"
              ? "Current-year topics are selected by default for a final assessment. Adjust to match what you taught."
              : "Current and prior-year topics are selected by default so the diagnostic can find earlier gaps."}
          </p>
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

      {topicIds.length > 0 && (
        <div>
          <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted mb-2">
            Selected topics (drag to reorder)
          </p>
          <div className="space-y-2">
            {topicIds.map((id, idx) => {
              const topic = allTopics.find((t) => t.curriculum_topic_id === id);
              if (!topic) return null;
              return (
                <div
                  key={id}
                  className="flex items-center gap-2 px-3 py-2 bg-white border border-brand-border rounded-lg"
                >
                  <span className="text-sm font-sans text-brand-ink flex-1">
                    {topic.topic_name}
                  </span>
                  <button
                    type="button"
                    aria-label="Move up"
                    disabled={idx === 0}
                    onClick={() => {
                      if (idx <= 0) return;
                      const next = [...topicIds];
                      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                      setTopicIds(next);
                    }}
                    className="text-brand-muted hover:text-brand-ink disabled:opacity-30 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
                  >
                    <ChevronUp className="w-4 h-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    aria-label="Move down"
                    disabled={idx === topicIds.length - 1}
                    onClick={() => {
                      if (idx >= topicIds.length - 1) return;
                      const next = [...topicIds];
                      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
                      setTopicIds(next);
                    }}
                    className="text-brand-muted hover:text-brand-ink disabled:opacity-30 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
                  >
                    <ChevronDown className="w-4 h-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove ${topic.topic_name}`}
                    onClick={() => toggleTopic(id)}
                    className="text-brand-muted hover:text-brand-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
                  >
                    <X className="w-4 h-4" aria-hidden="true" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* An assessment always needs at least one topic. With none available at all,
          proceeding would fail schema validation at Step 4 with a confusing error,
          so it is blocked here where the cause is visible. */}
      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={() => setStep(1)}>
          Back
        </Button>
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          disabled={isError || !canProceed}
          onClick={() => setStep(3)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
