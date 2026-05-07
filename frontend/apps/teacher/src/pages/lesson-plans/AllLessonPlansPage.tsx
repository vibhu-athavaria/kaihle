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
    });
    setSelectedTopicId(null);
    setSelectedSubtopicIds(new Set());
    onOpenChange(false);
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
          <p className="text-xs font-bold uppercase tracking-wide text-brand-muted mb-2">
            1. Choose a topic
          </p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {topics.length === 0 ? (
              <p className="text-sm text-brand-muted">
                No topics added to this class yet.
              </p>
            ) : (
              topics.map((t) => (
                <button
                  key={t.curriculum_topic_id}
                  type="button"
                  onClick={() => {
                    setSelectedTopicId(t.topic_id);
                    setSelectedSubtopicIds(new Set());
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    selectedTopicId === t.topic_id
                      ? "bg-brand-gold text-white font-semibold"
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
        {selectedTopicId && (
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-brand-muted mb-2">
              2. Select subtopics to focus on
            </p>
            {subtopicsLoading ? (
              <div className="animate-pulse space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-8 bg-brand-border rounded-lg" />
                ))}
              </div>
            ) : subtopics.length === 0 ? (
              <p className="text-sm text-brand-muted">
                No subtopics found for this topic.
              </p>
            ) : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {subtopics.map((s) => (
                  <label
                    key={s.id}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSubtopicIds.has(s.id)}
                      onChange={() => toggleSubtopic(s.id)}
                      className="w-4 h-4 rounded accent-brand-gold"
                    />
                    <span className="text-sm text-brand-ink">{s.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-1">
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
            disabled={selectedSubtopicIds.size === 0 || generate.isPending}
            className="px-4 py-2 text-sm font-bold text-white bg-brand-gold hover:bg-brand-gold-dark disabled:opacity-50 disabled:cursor-not-allowed rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            {generate.isPending ? "Starting…" : "Generate"}
          </button>
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
        Generating…
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

  return (
    <div className="bg-white rounded-xl border border-brand-border p-5 flex items-center justify-between gap-4">
      <div className="flex items-start gap-3 min-w-0">
        <BookOpen
          className="w-5 h-5 text-brand-gold mt-0.5 flex-shrink-0"
          aria-hidden="true"
        />
        <div className="min-w-0">
          <p className="font-semibold text-brand-ink text-sm truncate">
            Lesson Plan · {date}
          </p>
          <StatusBadge status={plan.status} />
          {plan.status === "ARCHIVED" && plan.failure_reason && (
            <p className="text-xs text-red-500 mt-1">{plan.failure_reason}</p>
          )}
        </div>
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
            Generate your first plan — pick the subtopics you want to focus on
            and the AI will build a differentiated 60-minute lesson.
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
