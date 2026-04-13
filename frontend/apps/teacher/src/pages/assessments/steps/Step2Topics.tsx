import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { Button, Skeleton } from "@kaihle/ui";
import { useAssessmentWizard } from "../../../hooks/useAssessmentWizard";

interface Topic {
  id: string;
  name: string;
}

async function fetchTopicsForClass(
  subjectId: string,
  gradeId: string,
  curriculumId: string
): Promise<Topic[]> {
  try {
    const res = await apiClient.get(`/api/v1/subjects/${subjectId}/topics`, {
      params: {
        curriculum_id: curriculumId,
        grade_id: gradeId,
      },
    });
    return (res.data || []).map((t: { id: string; name: string }) => ({
      id: t.id,
      name: t.name,
    }));
  } catch {
    return [];
  }
}

export function Step2Topics() {
  const { subjectId, gradeId, curriculumId, topicIds, setTopicIds, setStep } =
    useAssessmentWizard();

  const { data: topics = [], isLoading } = useQuery({
    queryKey: ["topics", subjectId, gradeId, curriculumId],
    queryFn: () =>
      fetchTopicsForClass(subjectId!, gradeId!, curriculumId!),
    enabled: !!subjectId && !!gradeId && !!curriculumId,
  });

  const canProceed = topicIds.length > 0;

  function toggleTopic(id: string) {
    if (topicIds.includes(id)) {
      setTopicIds(topicIds.filter((t) => t !== id));
    } else {
      setTopicIds([...topicIds, id]);
    }
  }

  function toggleAll() {
    if (topicIds.length === topics.length) {
      setTopicIds([]);
    } else {
      setTopicIds(topics.map((t) => t.id));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-sans font-semibold text-brand-ink">
            Select Topics
          </p>
          {topics.length > 0 && (
            <button
              type="button"
              onClick={toggleAll}
              className="text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
            >
              {topicIds.length === topics.length
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
        ) : topics.length === 0 ? (
          <div className="border border-brand-border rounded-xl p-6 text-center">
            <p className="text-sm font-sans text-brand-muted">
              No topics found for this class. You can continue — all available
              questions will be included.
            </p>
            <button
              type="button"
              onClick={() => setStep(3)}
              className="mt-3 text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
            >
              Skip to configuration →
            </button>
          </div>
        ) : (
          <div className="border border-brand-border rounded-xl divide-y divide-brand-border-soft overflow-hidden">
            {topics.map((topic) => {
              const checked = topicIds.includes(topic.id);
              return (
                <label
                  key={topic.id}
                  className={[
                    "flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors",
                    "hover:bg-brand-gold-light/30",
                    checked ? "bg-brand-gold-light/20" : "bg-white",
                  ].join(" ")}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleTopic(topic.id)}
                    className="w-4 h-4 rounded border-brand-border text-brand-gold focus:ring-brand-gold"
                    aria-label={topic.name}
                  />
                  <span className="text-sm font-sans text-brand-ink">
                    {topic.name}
                  </span>
                </label>
              );
            })}
          </div>
        )}

        {topics.length > 0 && !canProceed && (
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

      {/* Footer */}
      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={() => setStep(1)}>
          Back
        </Button>
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          disabled={topics.length > 0 && !canProceed}
          onClick={() => setStep(3)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
