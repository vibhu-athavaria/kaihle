import { useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Clock, RefreshCw, Filter } from "lucide-react";
import { useAuth } from "@kaihle/auth";
import { useTeacherClasses } from "../../hooks/useTeacherClasses";
import {
  useTeacherLessonPlans,
  useRegenerateLessonPlan,
  type LessonPlan,
} from "../../hooks/useLessonPlans";

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: LessonPlan["status"] }) {
  if (status === "GENERATING") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-brand-amber-light text-brand-amber animate-pulse">
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
  const label: Record<string, string> = {
    GENERATED: "Ready",
    EDITED: "Edited",
    USED: "Used",
    ARCHIVED: "Failed",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold ${map[status] ?? "bg-gray-100 text-brand-muted"}`}
    >
      {label[status] ?? status}
    </span>
  );
}

// ── Plan card ─────────────────────────────────────────────────────────────────

function LessonPlanRow({ plan }: { plan: LessonPlan }) {
  const retry = useRegenerateLessonPlan(plan.id, plan.class_id);

  const date = new Date(plan.generated_at).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const hook = plan.generated_plan?.lesson_hook ?? null;
  const conceptCount = plan.generated_plan?.key_concepts?.length ?? 0;
  const objectiveCount = plan.generated_plan?.learning_objectives?.length ?? 0;

  const byTopic = (plan.focus_subtopics ?? []).reduce<
    Record<string, typeof plan.focus_subtopics>
  >((acc, s) => {
    const key = s.topic_name || "Other";
    (acc[key] ??= []).push(s);
    return acc;
  }, {});
  const topicGroups = Object.entries(byTopic);

  const isGenerated =
    plan.status === "GENERATED" ||
    plan.status === "EDITED" ||
    plan.status === "USED";

  return (
    <div
      className={`bg-white rounded-xl border p-5 transition-shadow hover:shadow-sm ${
        plan.status === "ARCHIVED" ? "border-red-200" : "border-brand-border"
      }`}
    >
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4 mb-2">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <BookOpen
            className="w-4 h-4 text-brand-gold flex-shrink-0"
            aria-hidden="true"
          />
          <span className="font-semibold text-brand-ink text-sm">
            {plan.class_name}
          </span>
          <span className="text-brand-border text-xs">·</span>
          <span className="text-xs text-brand-muted">{date}</span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded-full text-[11px] font-semibold text-brand-ink">
            <Clock className="w-3 h-3 text-brand-muted" aria-hidden="true" />
            {plan.duration_minutes} min
          </span>
          <StatusBadge status={plan.status} />
        </div>

        {plan.status === "ARCHIVED" ? (
          <button
            type="button"
            onClick={() => retry.mutate()}
            disabled={retry.isPending}
            className="flex-shrink-0 px-3 py-1.5 text-xs font-bold text-white bg-red-500 hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-2"
          >
            {retry.isPending ? "Retrying…" : "Retry"}
          </button>
        ) : isGenerated ? (
          <Link
            to={`/teacher/classes/${plan.class_id}/lesson-plans/${plan.id}`}
            className="flex-shrink-0 px-3 py-1.5 text-xs font-bold text-white bg-brand-gold hover:bg-brand-gold-dark rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            View plan
          </Link>
        ) : null}
      </div>

      {/* ── Lesson hook ──────────────────────────────────────────── */}
      {hook && (
        <p className="text-sm text-brand-body leading-relaxed mb-2 line-clamp-2 italic">
          &ldquo;{hook}&rdquo;
        </p>
      )}

      {plan.status === "GENERATING" && (
        <p className="text-xs text-brand-muted mb-2">
          You'll receive an email when this plan is ready.
        </p>
      )}

      {plan.status === "ARCHIVED" && plan.failure_reason && (
        <p className="text-xs text-red-500 mb-2">{plan.failure_reason}</p>
      )}

      {/* ── Subtopics ─────────────────────────────────────────────── */}
      {topicGroups.length > 0 && (
        <div className="space-y-1.5 mb-2">
          {topicGroups.map(([topicName, subs]) => (
            <div
              key={topicName}
              className="flex flex-wrap items-center gap-1.5"
            >
              <span className="text-[10px] font-bold uppercase tracking-wide text-brand-muted">
                {topicName}
              </span>
              <span className="text-brand-border text-[10px]">·</span>
              {subs.map((s, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2 py-0.5 bg-gray-50 border border-brand-border rounded-full text-xs text-brand-ink"
                >
                  {s.name}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* ── Stats ─────────────────────────────────────────────────── */}
      {isGenerated && (conceptCount > 0 || objectiveCount > 0) && (
        <div className="flex items-center gap-3 pt-2.5 border-t border-brand-border mt-2.5">
          {conceptCount > 0 && (
            <span className="text-xs text-brand-muted">
              <span className="font-semibold text-brand-ink">
                {conceptCount}
              </span>{" "}
              {conceptCount === 1 ? "concept" : "concepts"}
            </span>
          )}
          {objectiveCount > 0 && (
            <span className="text-xs text-brand-muted">
              <span className="font-semibold text-brand-ink">
                {objectiveCount}
              </span>{" "}
              {objectiveCount === 1 ? "objective" : "objectives"}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────

function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-1 mt-6">
      <button
        type="button"
        onClick={() => onPage(page - 1)}
        disabled={page === 1}
        className="px-3 py-1.5 text-xs font-semibold rounded-full border border-brand-border text-brand-ink hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
      >
        ← Prev
      </button>
      {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPage(p)}
          className={`w-8 h-8 text-xs font-semibold rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
            p === page
              ? "bg-brand-gold text-white"
              : "border border-brand-border text-brand-ink hover:bg-gray-50"
          }`}
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        onClick={() => onPage(page + 1)}
        disabled={page === totalPages}
        className="px-3 py-1.5 text-xs font-semibold rounded-full border border-brand-border text-brand-ink hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
      >
        Next →
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 10;

export function TeacherLessonPlansPage() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [selectedClassId, setSelectedClassId] = useState<string | undefined>(
    undefined,
  );

  const { data: classes = [] } = useTeacherClasses(
    user?.school_id ?? null,
    false,
  );
  const { data, isLoading } = useTeacherLessonPlans(
    page,
    PAGE_SIZE,
    selectedClassId,
  );

  const plans = data?.data ?? [];
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  function handleClassFilter(classId: string) {
    setSelectedClassId(classId === "all" ? undefined : classId);
    setPage(1);
  }

  return (
    <div className="p-6">
      {/* ── Header ───────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            Lesson Plans
          </h1>
          {data && data.total > 0 && (
            <p className="text-xs text-brand-muted mt-0.5">
              {data.total} {data.total === 1 ? "plan" : "plans"}
              {selectedClassId ? " in this class" : " across all classes"}
            </p>
          )}
        </div>

        {/* Class filter */}
        {classes.length > 0 && (
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-brand-muted" aria-hidden="true" />
            <select
              value={selectedClassId ?? "all"}
              onChange={(e) => handleClassFilter(e.target.value)}
              className="text-sm border border-brand-border rounded-full px-3 py-1.5 text-brand-ink bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
              aria-label="Filter by class"
            >
              <option value="all">All classes</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* ── Content ─────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 bg-brand-border rounded-xl" />
          ))}
        </div>
      ) : plans.length === 0 ? (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-4" role="img" aria-label="lesson plans">
            📋
          </div>
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
            {selectedClassId
              ? "No plans for this class yet."
              : "No lesson plans yet."}
          </h3>
          <p className="text-sm text-brand-muted max-w-sm mx-auto mb-6">
            Generate plans from a class page — pick the subtopics you want to
            focus on and the AI will build a differentiated lesson.
          </p>
          <Link
            to="/teacher/classes"
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
          >
            Go to Classes →
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {plans.map((plan) => (
              <LessonPlanRow key={plan.id} plan={plan} />
            ))}
          </div>
          <Pagination page={page} totalPages={totalPages} onPage={setPage} />
        </>
      )}
    </div>
  );
}
