import { useParams, Link } from "react-router-dom";
import { RefreshCw, ChevronLeft } from "lucide-react";
import { useLessonPlan } from "../../hooks/useLessonPlans";

const SECTION_LABELS: Record<string, string> = {
  starter_10min: "Starter (10 min)",
  group_a_activity: "Group A — Needs Work",
  group_b_activity: "Group B — Developing",
  group_c_activity: "Group C — Extension",
  plenary_10min: "Plenary (10 min)",
  homework: "Homework",
  teacher_notes: "Teacher Notes",
};

const SECTION_ORDER = [
  "starter_10min",
  "group_a_activity",
  "group_b_activity",
  "group_c_activity",
  "plenary_10min",
  "homework",
  "teacher_notes",
];

export function LessonPlanDetailPage() {
  const { classId, planId } = useParams<{ classId: string; planId: string }>();
  const { data: plan, isLoading } = useLessonPlan(planId);

  if (isLoading) {
    return (
      <div className="p-6 animate-pulse space-y-4">
        <div className="h-6 bg-brand-border rounded w-48" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-24 bg-brand-border rounded-xl" />
        ))}
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="p-6">
        <p className="text-brand-muted text-sm">Lesson plan not found.</p>
      </div>
    );
  }

  const isGenerating = plan.status === "GENERATING";
  const content = plan.generated_plan ?? {};

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center gap-2 mb-6">
        <Link
          to={`/teacher/classes/${classId}/lesson-plans`}
          className="text-brand-muted hover:text-brand-ink transition-colors"
          aria-label="Back to lesson plans"
        >
          <ChevronLeft className="w-5 h-5" aria-hidden="true" />
        </Link>
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Lesson Plan
        </h1>
        {isGenerating && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-brand-amber-light text-brand-amber animate-pulse ml-2">
            <RefreshCw className="w-3 h-3 animate-spin" aria-hidden="true" />
            Generating…
          </span>
        )}
      </div>

      {isGenerating ? (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <RefreshCw
            className="w-8 h-8 text-brand-gold animate-spin mx-auto mb-4"
            aria-hidden="true"
          />
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
            Your lesson plan is being generated.
          </h3>
          <p className="text-sm text-brand-muted max-w-sm mx-auto">
            This usually takes under 30 seconds. This page will update
            automatically when it&apos;s ready.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {SECTION_ORDER.map((key) => {
            const text = content[key];
            if (!text) return null;
            return (
              <div
                key={key}
                className="bg-white rounded-xl border border-brand-border p-5"
              >
                <h2 className="font-semibold text-sm text-brand-gold mb-2">
                  {SECTION_LABELS[key]}
                </h2>
                <p className="text-sm text-brand-body leading-relaxed">
                  {text}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
