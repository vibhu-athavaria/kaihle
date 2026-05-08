import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BookOpen, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { Modal } from "@kaihle/ui";
import { useClassTopics } from "../../hooks/useClassTopics";
import {
  useClassLessonPlans,
  useGenerateLessonPlan,
  type LessonPlan,
} from "../../hooks/useLessonPlans";

// ── Subtopic fetching ─────────────────────────────────────────────────────────

interface Subtopic {
  id: string;
  name: string;
}

function useTopicSubtopics(topicId: string | null) {
  return useQuery<Subtopic[]>({
    queryKey: ["subtopics", "topic", topicId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/subtopics`, {
        params: { topic_id: topicId },
      });
      return res.data as Subtopic[];
    },
    enabled: !!topicId,
  });
}

// ── Generate modal ────────────────────────────────────────────────────────────

function GenerateLessonPlanModal({
  classId,
  open,
  onOpenChange,
}: {
  classId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: topics = [] } = useClassTopics(classId);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [selectedSubtopicIds, setSelectedSubtopicIds] = useState<Set<string>>(
    new Set(),
  );
  const [durationMinutes, setDurationMinutes] = useState(45);
  const { data: subtopics = [], isLoading: subtopicsLoading } =
    useTopicSubtopics(selectedTopicId);
  const generate = useGenerateLessonPlan(classId);

  function toggleSubtopic(id: string) {
    setSelectedSubtopicIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleGenerate() {
    await generate.mutateAsync({
      classId,
      focusSubtopicIds: Array.from(selectedSubtopicIds),
      durationMinutes,
    });
    setSelectedTopicId(null);
    setSelectedSubtopicIds(new Set());
    setDurationMinutes(45);
    onOpenChange(false);
  }

  const step1Done = !!selectedTopicId;
  const step2Done = selectedSubtopicIds.size > 0;
  const selectedTopicName = topics.find(
    (t) => t.topic_id === selectedTopicId,
  )?.topic_name;

  function selectAll() {
    setSelectedSubtopicIds(new Set(subtopics.map((s) => s.id)));
  }
  function clearAll() {
    setSelectedSubtopicIds(new Set());
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="New Lesson Plan"
      maxWidth="md"
    >
      <div className="space-y-5">
        {/* Step 1 — pick topic */}
        <div>
          {/* Step header */}
          <div className="flex items-center gap-2 mb-3">
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 transition-colors ${
                step1Done
                  ? "bg-brand-gold text-white"
                  : "bg-gray-100 text-brand-muted"
              }`}
              aria-hidden="true"
            >
              {step1Done ? "✓" : "1"}
            </span>
            <p className="text-xs font-bold uppercase tracking-wide text-brand-ink">
              Choose a topic
            </p>
            {step1Done && (
              <span className="text-xs text-brand-muted truncate">
                — {selectedTopicName}
              </span>
            )}
          </div>

          {/* Topic list */}
          <div className="rounded-lg border border-brand-border overflow-hidden max-h-44 overflow-y-auto">
            {topics.length === 0 ? (
              <p className="text-sm text-brand-muted px-4 py-3">
                No topics added to this class yet.
              </p>
            ) : (
              topics.map((t, i) => (
                <button
                  key={t.curriculum_topic_id}
                  type="button"
                  onClick={() => {
                    setSelectedTopicId(t.topic_id);
                    setSelectedSubtopicIds(new Set());
                  }}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-gold ${
                    i > 0 ? "border-t border-brand-border" : ""
                  } ${
                    selectedTopicId === t.topic_id
                      ? "bg-amber-50 text-brand-gold-dark font-semibold"
                      : "hover:bg-gray-50 text-brand-ink"
                  }`}
                >
                  {t.topic_name}
                </button>
              ))
            )}
          </div>
        </div>

        {/* Step 2 — pick subtopics */}
        {step1Done && (
          <div>
            {/* Step header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 transition-colors ${
                    step2Done
                      ? "bg-brand-gold text-white"
                      : "bg-gray-100 text-brand-muted"
                  }`}
                  aria-hidden="true"
                >
                  {step2Done ? "✓" : "2"}
                </span>
                <p className="text-xs font-bold uppercase tracking-wide text-brand-ink">
                  Focus subtopics
                </p>
                {step2Done && (
                  <span className="text-xs font-semibold text-brand-gold">
                    {selectedSubtopicIds.size} selected
                  </span>
                )}
              </div>
              {!subtopicsLoading && subtopics.length > 0 && (
                <button
                  type="button"
                  onClick={
                    selectedSubtopicIds.size === subtopics.length
                      ? clearAll
                      : selectAll
                  }
                  className="text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
                >
                  {selectedSubtopicIds.size === subtopics.length
                    ? "Clear all"
                    : "Select all"}
                </button>
              )}
            </div>

            {subtopicsLoading ? (
              <div className="animate-pulse space-y-px rounded-lg border border-brand-border overflow-hidden">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 bg-brand-border" />
                ))}
              </div>
            ) : subtopics.length === 0 ? (
              <p className="text-sm text-brand-muted px-1">
                No subtopics found for this topic.
              </p>
            ) : (
              <div className="rounded-lg border border-brand-border overflow-hidden max-h-48 overflow-y-auto">
                {subtopics.map((s, i) => {
                  const checked = selectedSubtopicIds.has(s.id);
                  return (
                    <label
                      key={s.id}
                      className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                        i > 0 ? "border-t border-brand-border" : ""
                      } ${checked ? "bg-amber-50" : "hover:bg-gray-50"}`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleSubtopic(s.id)}
                        className="w-4 h-4 rounded accent-brand-gold flex-shrink-0"
                      />
                      <span
                        className={`text-sm transition-colors ${
                          checked
                            ? "text-brand-gold-dark font-semibold"
                            : "text-brand-ink"
                        }`}
                      >
                        {s.name}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Step 3 — duration (only visible once subtopics chosen) */}
        {step1Done && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span
                className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 bg-gray-100 text-brand-muted"
                aria-hidden="true"
              >
                3
              </span>
              <p className="text-xs font-bold uppercase tracking-wide text-brand-ink">
                Lesson duration
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {[30, 45, 60, 75, 90].map((mins) => (
                <button
                  key={mins}
                  type="button"
                  onClick={() => setDurationMinutes(mins)}
                  className={`px-3 py-1.5 rounded-full text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
                    durationMinutes === mins
                      ? "bg-brand-gold text-white"
                      : "border border-brand-border text-brand-ink hover:bg-gray-50"
                  }`}
                >
                  {mins} min
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-brand-muted">
            {!step1Done
              ? "Select a topic to continue"
              : !step2Done
                ? "Select at least one subtopic"
                : `${selectedSubtopicIds.size} subtopic${selectedSubtopicIds.size === 1 ? "" : "s"} · ${durationMinutes} min`}
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="px-4 py-2 text-sm font-semibold text-brand-ink border border-brand-border rounded-full hover:bg-gray-50 transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={!step2Done || generate.isPending}
              className="px-4 py-2 text-sm font-bold text-white bg-brand-gold hover:bg-brand-gold-dark disabled:opacity-40 disabled:cursor-not-allowed rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
            >
              {generate.isPending ? "Starting…" : "Generate"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: LessonPlan["status"] }) {
  if (status === "GENERATING") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-brand-amber-light text-brand-amber animate-pulse">
        <RefreshCw className="w-3 h-3 animate-spin" aria-hidden="true" />
        Generating — you'll be emailed when ready
      </span>
    );
  }
  const map: Record<string, string> = {
    GENERATED: "bg-brand-green-light text-brand-green",
    EDITED: "bg-blue-50 text-blue-700",
    USED: "bg-gray-100 text-brand-muted",
    ARCHIVED: "bg-red-50 text-red-600",
  };
  return (
    <span
      className={`inline-flex px-2.5 py-1 rounded-full text-xs font-semibold ${map[status] ?? "bg-gray-100 text-brand-muted"}`}
    >
      {status === "ARCHIVED"
        ? "Failed"
        : status.charAt(0) + status.slice(1).toLowerCase()}
    </span>
  );
}

// ── Plan card ─────────────────────────────────────────────────────────────────

function LessonPlanCard({
  plan,
  classId,
}: {
  plan: LessonPlan;
  classId: string;
}) {
  const date = new Date(plan.generated_at).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  // Group subtopics by topic_name — preserves insertion order
  const byTopic = (plan.focus_subtopics ?? []).reduce<
    Record<string, typeof plan.focus_subtopics>
  >((acc, s) => {
    const key = s.topic_name || "Other";
    (acc[key] ??= []).push(s);
    return acc;
  }, {});
  const topicGroups = Object.entries(byTopic);

  return (
    <div className="bg-white rounded-xl border border-brand-border p-5">
      {/* Top row — date, status, action */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <BookOpen
            className="w-4 h-4 text-brand-gold flex-shrink-0"
            aria-hidden="true"
          />
          <span className="font-semibold text-brand-ink text-sm">{date}</span>
          <StatusBadge status={plan.status} />
        </div>
        {plan.status !== "GENERATING" && plan.status !== "ARCHIVED" && (
          <Link
            to={`/teacher/classes/${classId}/lesson-plans/${plan.id}`}
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark flex-shrink-0 focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
          >
            View →
          </Link>
        )}
      </div>

      {/* Topics + subtopics grouped */}
      {topicGroups.length > 0 && (
        <div className="space-y-2.5">
          {topicGroups.map(([topicName, subs]) => (
            <div key={topicName}>
              <p className="text-[10px] font-bold uppercase tracking-wide text-brand-muted mb-1.5">
                {topicName}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {subs.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center px-2.5 py-1 bg-gray-50 border border-brand-border rounded-full text-xs text-brand-ink"
                  >
                    {s.name}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Failure reason */}
      {plan.status === "ARCHIVED" && plan.failure_reason && (
        <p className="text-xs text-red-500 mt-2">{plan.failure_reason}</p>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function AllLessonPlansPage() {
  const { classId } = useParams<{ classId: string }>();
  const { data, isLoading } = useClassLessonPlans(classId);
  const [modalOpen, setModalOpen] = useState(false);

  const plans = data?.data ?? [];

  if (!classId) {
    return (
      <div className="p-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
          Lesson Plans
        </h1>
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-4" role="img" aria-label="lesson plans">
            📋
          </div>
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
            Select a class to view its lesson plans.
          </h3>
          <p className="text-sm text-brand-muted max-w-sm mx-auto mb-6">
            Lesson plans are generated on-demand — pick a class and choose which
            subtopics to focus on.
          </p>
          <Link
            to="/teacher/classes"
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
          >
            Go to Classes →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Lesson Plans
        </h1>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="bg-brand-gold text-white text-xs font-bold px-4 py-2 rounded-full hover:bg-brand-gold-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
        >
          + New Lesson Plan
        </button>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-brand-border rounded-xl" />
          ))}
        </div>
      ) : plans.length === 0 ? (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-4" role="img" aria-label="lesson plans">
            📋
          </div>
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
            No lesson plans yet.
          </h3>
          <p className="text-sm text-brand-muted max-w-sm mx-auto mb-6">
            Generate your first plan — pick the subtopics you want to focus on,
            choose a duration, and the AI will build a differentiated lesson.
          </p>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
          >
            Generate a Lesson Plan →
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {plans.map((plan) => (
            <LessonPlanCard key={plan.id} plan={plan} classId={classId} />
          ))}
        </div>
      )}

      <GenerateLessonPlanModal
        classId={classId}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
