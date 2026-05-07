import { useParams, Link } from "react-router-dom";
import {
  RefreshCw,
  ChevronLeft,
  Clock,
  BookOpen,
  Lightbulb,
  AlertCircle,
} from "lucide-react";
import { useLessonPlan } from "../../hooks/useLessonPlans";

// ── Helpers ────────────────────────────────────────────────────────────────────

function SectionCard({
  title,
  duration,
  children,
  accent = "gold",
}: {
  title: string;
  duration?: number;
  children: React.ReactNode;
  accent?: "gold" | "green" | "blue" | "purple";
}) {
  const accentMap = {
    gold: "border-l-brand-gold text-brand-gold",
    green: "border-l-brand-green text-brand-green",
    blue: "border-l-blue-500 text-blue-600",
    purple: "border-l-purple-500 text-purple-600",
  };
  return (
    <div className="bg-white rounded-xl border border-brand-border p-5">
      <div
        className={`flex items-center justify-between mb-3 border-l-4 pl-3 ${accentMap[accent]}`}
      >
        <h2 className="font-semibold text-sm">{title}</h2>
        {duration != null && (
          <span className="inline-flex items-center gap-1 text-xs text-brand-muted font-medium">
            <Clock className="w-3.5 h-3.5" aria-hidden="true" />
            {duration} min
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function StringList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-brand-body">
          <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-gold flex-shrink-0" />
          {item}
        </li>
      ))}
    </ul>
  );
}

function GroupBand({
  label,
  bandLabel,
  duration,
  activity,
  extra,
  color,
}: {
  label: string;
  bandLabel: string;
  duration?: number;
  activity: string;
  extra?: string;
  color: "red" | "amber" | "green";
}) {
  const colorMap = {
    red: {
      bg: "bg-red-50",
      badge: "bg-red-100 text-red-700",
      dot: "bg-brand-red",
    },
    amber: {
      bg: "bg-amber-50",
      badge: "bg-amber-100 text-amber-700",
      dot: "bg-brand-amber",
    },
    green: {
      bg: "bg-brand-green-light",
      badge: "bg-brand-green-light text-brand-green",
      dot: "bg-brand-green",
    },
  };
  const c = colorMap[color];
  return (
    <div className={`rounded-lg p-4 ${c.bg}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${c.dot}`}
            aria-hidden="true"
          />
          <span
            className={`text-xs font-bold px-2 py-0.5 rounded-full ${c.badge}`}
          >
            {bandLabel}
          </span>
          {label && <span className="text-xs text-brand-muted">{label}</span>}
        </div>
        {duration != null && (
          <span className="text-xs text-brand-muted flex items-center gap-1">
            <Clock className="w-3 h-3" aria-hidden="true" />
            {duration} min
          </span>
        )}
      </div>
      <p className="text-sm text-brand-body leading-relaxed">{activity}</p>
      {extra && (
        <p className="mt-2 text-xs text-brand-muted italic">
          <span className="font-semibold not-italic text-brand-ink">
            Extension:{" "}
          </span>
          {extra}
        </p>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const c = (plan.generated_plan ?? {}) as Record<string, any>;

  return (
    <div className="p-6 max-w-3xl">
      {/* Header */}
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
          {/* Learning objectives */}
          {Array.isArray(c.learning_objectives) &&
            c.learning_objectives.length > 0 && (
              <SectionCard title="Learning Objectives" accent="gold">
                <StringList items={c.learning_objectives as string[]} />
              </SectionCard>
            )}

          {/* Prior knowledge */}
          {c.prior_knowledge && (
            <SectionCard title="Prior Knowledge" accent="blue">
              <p className="text-sm text-brand-body leading-relaxed">
                {String(c.prior_knowledge)}
              </p>
            </SectionCard>
          )}

          {/* Starter */}
          {c.starter && (
            <SectionCard
              title="Starter"
              duration={
                (c.starter as Record<string, unknown>).duration_minutes as
                  | number
                  | undefined
              }
              accent="gold"
            >
              <p className="text-sm text-brand-body leading-relaxed">
                {String((c.starter as Record<string, unknown>).activity ?? "")}
              </p>
              {!!(c.starter as Record<string, unknown>).purpose && (
                <p className="mt-2 text-xs text-brand-muted italic">
                  <span className="font-semibold not-italic text-brand-ink">
                    Purpose:{" "}
                  </span>
                  {String((c.starter as Record<string, unknown>).purpose)}
                </p>
              )}
            </SectionCard>
          )}

          {/* Key concepts */}
          {Array.isArray(c.key_concepts) && c.key_concepts.length > 0 && (
            <SectionCard title="Key Concepts" accent="blue">
              <div className="space-y-2">
                {(c.key_concepts as Array<Record<string, string>>).map(
                  (kc, i) => (
                    <div key={i} className="flex gap-2 text-sm">
                      <span className="font-semibold text-brand-ink min-w-[120px]">
                        {kc.term}
                      </span>
                      <span className="text-brand-body">{kc.definition}</span>
                    </div>
                  ),
                )}
              </div>
            </SectionCard>
          )}

          {/* Real-world applications */}
          {Array.isArray(c.real_world_applications) &&
            c.real_world_applications.length > 0 && (
              <SectionCard title="Real-World Applications" accent="green">
                <div className="space-y-3">
                  {(
                    c.real_world_applications as Array<Record<string, string>>
                  ).map((app, i) => (
                    <div key={i} className="flex gap-3">
                      <Lightbulb
                        className="w-4 h-4 text-brand-gold flex-shrink-0 mt-0.5"
                        aria-hidden="true"
                      />
                      <div>
                        {app.title && (
                          <p className="text-sm font-semibold text-brand-ink">
                            {app.title}
                          </p>
                        )}
                        <p className="text-sm text-brand-body leading-relaxed">
                          {app.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

          {/* Differentiated main activity */}
          {c.main_activity && (
            <SectionCard
              title="Main Activity — Differentiated Groups"
              accent="gold"
            >
              <div className="space-y-3">
                {!!(c.main_activity as Record<string, unknown>)
                  .group_foundation && (
                  <GroupBand
                    bandLabel="Needs Work"
                    label={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .group_foundation as Record<string, unknown>
                      ).label ?? "",
                    )}
                    duration={
                      (
                        (c.main_activity as Record<string, unknown>)
                          .group_foundation as Record<string, unknown>
                      ).duration_minutes as number | undefined
                    }
                    activity={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .group_foundation as Record<string, unknown>
                      ).activity ?? "",
                    )}
                    extra={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .group_foundation as Record<string, unknown>
                      ).support ?? "",
                    )}
                    color="red"
                  />
                )}
                {!!(c.main_activity as Record<string, unknown>).core && (
                  <GroupBand
                    bandLabel="Developing"
                    label={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .core as Record<string, unknown>
                      ).label ?? "",
                    )}
                    duration={
                      (
                        (c.main_activity as Record<string, unknown>)
                          .core as Record<string, unknown>
                      ).duration_minutes as number | undefined
                    }
                    activity={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .core as Record<string, unknown>
                      ).activity ?? "",
                    )}
                    extra={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .core as Record<string, unknown>
                      ).extension_prompt ?? "",
                    )}
                    color="amber"
                  />
                )}
                {!!(c.main_activity as Record<string, unknown>).extension && (
                  <GroupBand
                    bandLabel="Strong"
                    label={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .extension as Record<string, unknown>
                      ).label ?? "",
                    )}
                    duration={
                      (
                        (c.main_activity as Record<string, unknown>)
                          .extension as Record<string, unknown>
                      ).duration_minutes as number | undefined
                    }
                    activity={String(
                      (
                        (c.main_activity as Record<string, unknown>)
                          .extension as Record<string, unknown>
                      ).activity ?? "",
                    )}
                    color="green"
                  />
                )}
              </div>
            </SectionCard>
          )}

          {/* Formative check */}
          {c.formative_check && (
            <SectionCard
              title="Formative Check"
              duration={
                (c.formative_check as Record<string, unknown>)
                  .duration_minutes as number | undefined
              }
              accent="purple"
            >
              <p className="text-sm font-semibold text-brand-ink mb-1">
                {String(
                  (c.formative_check as Record<string, unknown>).method ?? "",
                )}
              </p>
              {!!(c.formative_check as Record<string, unknown>)
                .what_to_look_for && (
                <p className="text-xs text-brand-muted">
                  <span className="font-semibold text-brand-body">
                    Look for:{" "}
                  </span>
                  {String(
                    (c.formative_check as Record<string, unknown>)
                      .what_to_look_for,
                  )}
                </p>
              )}
            </SectionCard>
          )}

          {/* Plenary */}
          {c.plenary && (
            <SectionCard
              title="Plenary"
              duration={
                (c.plenary as Record<string, unknown>).duration_minutes as
                  | number
                  | undefined
              }
              accent="gold"
            >
              <p className="text-sm text-brand-body leading-relaxed">
                {String((c.plenary as Record<string, unknown>).activity ?? "")}
              </p>
            </SectionCard>
          )}

          {/* Homework */}
          {c.homework && (
            <SectionCard title="Homework" accent="blue">
              <p className="text-sm text-brand-body leading-relaxed">
                {String(c.homework)}
              </p>
            </SectionCard>
          )}

          {/* Resources needed */}
          {Array.isArray(c.resources_needed) &&
            c.resources_needed.length > 0 && (
              <SectionCard title="Resources Needed" accent="gold">
                <div className="flex flex-wrap gap-2">
                  {(c.resources_needed as string[]).map((r, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-100 text-brand-ink text-xs font-medium rounded-full"
                    >
                      <BookOpen
                        className="w-3 h-3 text-brand-muted"
                        aria-hidden="true"
                      />
                      {r}
                    </span>
                  ))}
                </div>
              </SectionCard>
            )}

          {/* Common misconceptions */}
          {Array.isArray(c.common_misconceptions) &&
            c.common_misconceptions.length > 0 && (
              <SectionCard title="Common Misconceptions" accent="purple">
                <div className="space-y-2">
                  {(c.common_misconceptions as string[]).map((m, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <AlertCircle
                        className="w-4 h-4 text-purple-500 flex-shrink-0 mt-0.5"
                        aria-hidden="true"
                      />
                      <p className="text-sm text-brand-body leading-relaxed">
                        {m}
                      </p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

          {/* Teacher tips */}
          {c.teacher_tips && (
            <div className="bg-brand-amber-light border border-amber-200 rounded-xl p-5">
              <h2 className="font-semibold text-sm text-amber-700 mb-2">
                Teacher Tips
              </h2>
              <p className="text-sm text-amber-800 leading-relaxed">
                {String(c.teacher_tips)}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
