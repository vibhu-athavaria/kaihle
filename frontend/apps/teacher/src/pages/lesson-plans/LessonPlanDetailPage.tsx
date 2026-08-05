import { useParams, Link } from "react-router-dom";
import {
  ChevronLeft,
  Clock,
  BookOpen,
  AlertTriangle,
  HelpCircle,
  Zap,
  CheckCircle2,
} from "lucide-react";
import {
  useLessonPlan,
  type LessonPlan,
  type LessonPlanContent,
  type LessonPlanConcept,
  type ClassContextSnapshot,
} from "../../hooks/useLessonPlans";

// ── Learning-style sidebar ─────────────────────────────────────────────────────

function ModalityBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-xs text-brand-body capitalize">{label}</span>
        <span className="text-xs font-semibold text-brand-ink">{pct}%</span>
      </div>
      <div className="w-full bg-brand-border rounded-full h-1.5">
        <div
          className="bg-brand-gold h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label} ${pct}%`}
        />
      </div>
    </div>
  );
}

function LearningStyleSidebar({
  snapshot,
  durationMinutes,
  timeBreakdown,
}: {
  snapshot: ClassContextSnapshot | null | undefined;
  durationMinutes: number | null;
  timeBreakdown: LessonPlanContent["time_breakdown"] | null;
}) {
  const modalities = Object.entries(snapshot?.modality_distribution ?? {}).sort(
    ([, a], [, b]) => b - a,
  );

  const phases = timeBreakdown
    ? [
        {
          label: "Starter",
          min: timeBreakdown.starter_minutes,
          color: "bg-brand-gold",
        },
        {
          label: "Introduction",
          min: timeBreakdown.intro_minutes,
          color: "bg-blue-400",
        },
        {
          label: "Group activity",
          min: timeBreakdown.activity_minutes,
          color: "bg-brand-primary",
        },
        {
          label: "Exit ticket",
          min: timeBreakdown.exit_ticket_minutes,
          color: "bg-purple-400",
        },
        {
          label: "Plenary",
          min: timeBreakdown.plenary_minutes,
          color: "bg-brand-amber",
        },
      ]
    : [];

  const phaseTotal = phases.reduce((s, p) => s + p.min, 0);
  const total = (durationMinutes ?? phaseTotal) || 1;

  return (
    <aside className="w-[240px] flex-shrink-0 space-y-5">
      {/* Time flow */}
      {phases.length > 0 && (
        <div className="bg-white rounded-xl border border-brand-border p-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-brand-muted mb-3">
            Time flow
          </h3>
          {/* Stacked bar */}
          <div className="flex h-2 rounded-full overflow-hidden mb-3 gap-px">
            {phases.map((p) => (
              <div
                key={p.label}
                className={`${p.color} transition-all`}
                style={{ width: `${(p.min / total) * 100}%` }}
                aria-label={`${p.label} ${p.min} minutes`}
              />
            ))}
          </div>
          <div className="space-y-1.5">
            {phases.map((p) => (
              <div key={p.label} className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${p.color}`}
                  aria-hidden="true"
                />
                <span className="text-xs text-brand-body flex-1">
                  {p.label}
                </span>
                <span className="text-xs font-semibold text-brand-ink tabular-nums">
                  {p.min}m
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning style */}
      {modalities.length > 0 && (
        <div className="bg-white rounded-xl border border-brand-border p-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-brand-muted mb-3">
            Class learning style
          </h3>
          <div className="space-y-2.5">
            {modalities.map(([key, val]) => (
              <ModalityBar
                key={key}
                label={key.replace("_", " ")}
                score={val}
              />
            ))}
          </div>
          {(snapshot?.student_count ?? 0) > 0 && (
            <p className="mt-3 text-[10px] text-brand-muted">
              Based on {snapshot!.student_count} student
              {snapshot!.student_count !== 1 ? "s" : ""}
            </p>
          )}
        </div>
      )}

      {/* Interests */}
      {(snapshot?.top_interests ?? []).length > 0 && (
        <div className="bg-white rounded-xl border border-brand-border p-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-brand-muted mb-3">
            Class interests
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {snapshot!.top_interests.map((interest) => (
              <span
                key={interest}
                className="inline-block px-2 py-0.5 bg-brand-gold/10 text-brand-gold-dark text-xs font-medium rounded-full"
              >
                {interest}
              </span>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}

// ── Concept card ───────────────────────────────────────────────────────────────

function ConceptCard({
  concept,
  index,
}: {
  concept: LessonPlanConcept;
  index: number;
}) {
  return (
    <div className="bg-white rounded-xl border border-brand-border p-5">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
            {index + 1}
          </span>
          <h3 className="font-semibold text-sm text-brand-ink">
            {concept.name}
          </h3>
        </div>
        <span className="inline-flex items-center gap-1 text-xs text-brand-muted">
          <Clock className="w-3 h-3" aria-hidden="true" />
          {concept.duration_minutes}m
        </span>
      </div>

      <div className="space-y-2 mb-4">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted">
            Teacher does
          </span>
          <p className="text-sm text-brand-body mt-0.5">
            {concept.teacher_does}
          </p>
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted">
            Students do
          </span>
          <p className="text-sm text-brand-body mt-0.5">
            {concept.student_does}
          </p>
        </div>
      </div>

      <div className="bg-blue-50 rounded-lg p-3 mb-3">
        <div className="flex items-start gap-2">
          <HelpCircle
            className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600">
              Check question
            </span>
            <p className="text-sm text-blue-800 mt-0.5">
              {concept.check_question}
            </p>
          </div>
        </div>
      </div>

      <div className="bg-amber-50 rounded-lg p-3">
        <div className="flex items-start gap-2">
          <AlertTriangle
            className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600">
              Common misconception
            </span>
            <p className="text-xs text-amber-800">
              <span className="font-semibold">Students say: </span>
              &ldquo;{concept.misconception.trigger_phrase}&rdquo;
            </p>
            <p className="text-xs text-amber-700">
              <span className="font-semibold">Recovery: </span>
              {concept.misconception.recovery_script}
            </p>
          </div>
        </div>
      </div>

      {concept.transition_cue && (
        <p className="mt-3 text-xs text-brand-muted italic border-t border-brand-border pt-2">
          <span className="font-semibold not-italic text-brand-body">
            Transition:{" "}
          </span>
          {concept.transition_cue}
        </p>
      )}
    </div>
  );
}

// ── Group activity grid ────────────────────────────────────────────────────────

function GroupActivityGrid({
  activities,
}: {
  activities: LessonPlanContent["group_activities"];
}) {
  const groups = [
    {
      key: "foundation" as const,
      label: "Foundation",
      bg: "bg-red-50",
      badge: "bg-red-100 text-red-700",
      dot: "bg-brand-red",
    },
    {
      key: "core" as const,
      label: "Core",
      bg: "bg-amber-50",
      badge: "bg-amber-100 text-amber-700",
      dot: "bg-brand-amber",
    },
    {
      key: "extension" as const,
      label: "Extension",
      bg: "bg-brand-green-light",
      badge: "bg-brand-green-light text-brand-green",
      dot: "bg-brand-green",
    },
  ];

  return (
    <div className="space-y-3">
      {groups.map(({ key, label, bg, badge, dot }) => {
        const activity = activities[key];
        return (
          <div key={key} className={`rounded-lg p-4 ${bg}`}>
            <div className="flex items-center gap-2 mb-2">
              <span
                className={`w-2 h-2 rounded-full ${dot}`}
                aria-hidden="true"
              />
              <span
                className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge}`}
              >
                {label}
              </span>
            </div>
            <p className="text-sm text-brand-body leading-relaxed mb-2">
              {activity.description}
            </p>
            <p className="text-xs text-brand-muted italic">
              <span className="font-semibold not-italic text-brand-body">
                If stuck:{" "}
              </span>
              &ldquo;{activity.stuck_prompt}&rdquo;
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ── Exit ticket card ───────────────────────────────────────────────────────────

function ExitTicketCard({
  exitTicket,
}: {
  exitTicket: LessonPlanContent["exit_ticket"];
}) {
  if (!exitTicket.questions.length) return null;
  return (
    <div className="space-y-3">
      {exitTicket.questions.map((q, i) => (
        <div
          key={i}
          className="bg-purple-50 rounded-xl border border-purple-100 p-4"
        >
          <div className="flex items-start gap-2 mb-3">
            <CheckCircle2
              className="w-4 h-4 text-purple-500 flex-shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-purple-500">
                {q.label}
              </span>
              <p className="text-sm font-semibold text-brand-ink mt-0.5">
                {q.question_text}
              </p>
            </div>
          </div>
          <div className="space-y-1.5 pl-6">
            <p className="text-xs text-purple-700">
              <span className="font-semibold">Good answer: </span>
              {q.good_answer}
            </p>
            <p className="text-xs text-brand-muted">
              <span className="font-semibold text-brand-body">
                If most are wrong:{" "}
              </span>
              {q.pivot_if_wrong}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Phase divider ──────────────────────────────────────────────────────────────

function PhaseDivider({
  title,
  minutes,
  icon: Icon,
}: {
  title: string;
  minutes: number;
  icon: React.ElementType;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2 text-brand-muted">
        <Icon className="w-4 h-4" aria-hidden="true" />
        <span className="text-xs font-bold uppercase tracking-wider">
          {title}
        </span>
        <span className="text-xs font-semibold tabular-nums">{minutes}m</span>
      </div>
      <div className="flex-1 h-px bg-brand-border" />
    </div>
  );
}

// ── Header title ───────────────────────────────────────────────────────────────

/**
 * Titles the plan by what it actually teaches: "Grade 7 — Forces" with the parent
 * topic underneath. Falls back through grade → class name → generic label so a
 * plan with no grade or no focus subtopics still gets a meaningful heading.
 */
function LessonPlanTitle({ plan }: { plan: LessonPlan }) {
  const subtopics = plan.focus_subtopics ?? [];
  const subtopicNames = subtopics.map((s) => s.name).filter(Boolean);
  const topicNames = [
    ...new Set(subtopics.map((s) => s.topic_name).filter(Boolean)),
  ];

  const scope = plan.grade_name ?? plan.class_name;
  const heading =
    subtopicNames.length > 0
      ? `${scope} — ${subtopicNames.join(" · ")}`
      : (scope ?? "Lesson Plan");

  return (
    <div className="min-w-0">
      <h1 className="font-display font-bold text-2xl text-brand-ink truncate">
        {heading}
      </h1>
      {topicNames.length > 0 && (
        <p className="text-sm text-brand-body truncate">
          {topicNames.join(" · ")}
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
        {[1, 2, 3, 4].map((i) => (
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
  const c: LessonPlanContent | null = plan.generated_plan;

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Link
          to={`/teacher/classes/${classId}/lesson-plans`}
          className="text-brand-muted hover:text-brand-ink transition-colors flex-shrink-0"
          aria-label="Back to lesson plans"
        >
          <ChevronLeft className="w-5 h-5" aria-hidden="true" />
        </Link>
        <LessonPlanTitle plan={plan} />
        {isGenerating && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-brand-amber-light text-brand-amber animate-pulse ml-2 flex-shrink-0">
            Generating — you&apos;ll be emailed when ready
          </span>
        )}
      </div>

      {isGenerating ? (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center max-w-md">
          <div className="w-10 h-10 rounded-full bg-brand-amber-light flex items-center justify-center mx-auto mb-4">
            <Clock className="w-5 h-5 text-brand-amber" aria-hidden="true" />
          </div>
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
            Generating your lesson plan
          </h3>
          <p className="text-sm text-brand-muted max-w-xs mx-auto">
            This usually takes 1–2 minutes. You&apos;ll receive an email when
            it&apos;s ready — no need to stay on this page.
          </p>
        </div>
      ) : c ? (
        <div className="flex gap-6 items-start">
          {/* Sidebar */}
          <LearningStyleSidebar
            snapshot={plan.class_context_snapshot}
            durationMinutes={null}
            timeBreakdown={c.time_breakdown}
          />

          {/* Main content */}
          <div className="flex-1 min-w-0 space-y-5">
            {/* Lesson hook */}
            {c.lesson_hook && (
              <div className="bg-brand-gold/10 border border-brand-gold/20 rounded-xl p-5">
                <div className="flex items-start gap-3">
                  <Zap
                    className="w-5 h-5 text-brand-gold flex-shrink-0 mt-0.5"
                    aria-hidden="true"
                  />
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-brand-gold">
                      Lesson hook
                    </span>
                    <p className="text-base font-semibold text-brand-ink mt-1 leading-snug">
                      {c.lesson_hook}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Learning objectives */}
            {c.learning_objectives.length > 0 && (
              <div className="bg-white rounded-xl border border-brand-border p-5">
                <h2 className="font-semibold text-sm text-brand-ink mb-3 flex items-center gap-2">
                  <span
                    className="w-1 h-4 rounded-full bg-brand-gold"
                    aria-hidden="true"
                  />
                  Learning Objectives
                </h2>
                <ul className="space-y-1.5">
                  {c.learning_objectives.map((obj, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-brand-body"
                    >
                      <span
                        className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-gold flex-shrink-0"
                        aria-hidden="true"
                      />
                      {obj}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Prior knowledge */}
            {c.prior_knowledge && (
              <div className="bg-white rounded-xl border border-brand-border p-5">
                <h2 className="font-semibold text-sm text-brand-ink mb-2 flex items-center gap-2">
                  <span
                    className="w-1 h-4 rounded-full bg-blue-400"
                    aria-hidden="true"
                  />
                  Prior Knowledge
                </h2>
                <p className="text-sm text-brand-body">{c.prior_knowledge}</p>
              </div>
            )}

            {/* Starter */}
            <PhaseDivider
              title="Starter"
              minutes={c.starter.duration_minutes}
              icon={Clock}
            />
            <div className="bg-white rounded-xl border border-brand-border p-5">
              <p className="text-sm text-brand-body leading-relaxed">
                {c.starter.activity}
              </p>
            </div>

            {/* Key concepts */}
            {c.key_concepts.length > 0 && (
              <>
                <PhaseDivider
                  title="Key Concepts"
                  minutes={c.time_breakdown.intro_minutes}
                  icon={BookOpen}
                />
                <div className="space-y-4">
                  {c.key_concepts.map((concept, i) => (
                    <ConceptCard key={i} concept={concept} index={i} />
                  ))}
                </div>
              </>
            )}

            {/* Group activities */}
            <PhaseDivider
              title="Group Activity"
              minutes={c.time_breakdown.activity_minutes}
              icon={Clock}
            />
            <div className="bg-white rounded-xl border border-brand-border p-5">
              <GroupActivityGrid activities={c.group_activities} />
            </div>

            {/* Exit ticket */}
            <PhaseDivider
              title="Exit Ticket"
              minutes={c.time_breakdown.exit_ticket_minutes}
              icon={CheckCircle2}
            />
            <ExitTicketCard exitTicket={c.exit_ticket} />

            {/* Plenary */}
            <PhaseDivider
              title="Plenary"
              minutes={c.plenary.duration_minutes}
              icon={Clock}
            />
            <div className="bg-white rounded-xl border border-brand-border p-5">
              <p className="text-sm text-brand-body leading-relaxed">
                {c.plenary.activity}
              </p>
            </div>

            {/* Resources */}
            {c.resources_needed.length > 0 && (
              <div className="bg-white rounded-xl border border-brand-border p-5">
                <h2 className="font-semibold text-sm text-brand-ink mb-3 flex items-center gap-2">
                  <span
                    className="w-1 h-4 rounded-full bg-brand-gold"
                    aria-hidden="true"
                  />
                  Resources Needed
                </h2>
                <div className="flex flex-wrap gap-2">
                  {c.resources_needed.map((r, i) => (
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
              </div>
            )}

            {/* Homework */}
            {c.homework && (
              <div className="bg-white rounded-xl border border-brand-border p-5">
                <h2 className="font-semibold text-sm text-brand-ink mb-2 flex items-center gap-2">
                  <span
                    className="w-1 h-4 rounded-full bg-blue-400"
                    aria-hidden="true"
                  />
                  Homework
                </h2>
                <p className="text-sm text-brand-body">{c.homework}</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-brand-border p-8 text-center">
          <p className="text-sm text-brand-muted">No plan content available.</p>
        </div>
      )}
    </div>
  );
}
