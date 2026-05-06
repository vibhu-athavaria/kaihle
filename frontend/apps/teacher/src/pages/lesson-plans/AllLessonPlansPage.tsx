import { Link, useParams } from "react-router-dom";
import { BookOpen, RefreshCw } from "lucide-react";
import {
  useClassLessonPlans,
  type LessonPlan,
} from "../../hooks/useLessonPlans";

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
    ARCHIVED: "bg-gray-100 text-brand-muted",
  };
  return (
    <span
      className={`inline-flex px-2.5 py-1 rounded-full text-xs font-semibold ${map[status] ?? "bg-gray-100 text-brand-muted"}`}
    >
      {status.charAt(0) + status.slice(1).toLowerCase()}
    </span>
  );
}

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
        </div>
      </div>
      {plan.status !== "GENERATING" && (
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

export function AllLessonPlansPage() {
  const { classId } = useParams<{ classId: string }>();
  const { data, isLoading } = useClassLessonPlans(classId);

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
            Lesson plans are generated on-demand from a class&apos;s gap map.
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
          disabled
          className="bg-brand-gold text-white text-xs font-bold px-4 py-2 rounded-full opacity-50 cursor-not-allowed"
          title="Coming soon"
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
            Generate a plan from the gap map to get started. Each plan is built
            around your students&apos; lowest-mastery subtopics.
          </p>
          <Link
            to={`/teacher/classes/${classId}/gap-map`}
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
          >
            View Gap Map →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {plans.map((plan) => (
            <LessonPlanCard key={plan.id} plan={plan} classId={classId} />
          ))}
        </div>
      )}
    </div>
  );
}
