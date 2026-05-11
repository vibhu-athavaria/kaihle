import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ExternalLink, CheckCircle } from "lucide-react";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useStudyPlan } from "../../hooks/useStudyPlan";
import { useMarkResourceWatched } from "../../hooks/useMarkResourceWatched";
import {
  useSubmitStudyPlanQuiz,
  type QuizResult,
} from "../../hooks/useSubmitStudyPlanQuiz";
import type {
  StudyPlanResource,
  StudyPlanQuizQuestion,
} from "../../hooks/useMyStudyPlans";

export function StudyPlanDetail() {
  const { planId = "" } = useParams<{ planId: string }>();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();
  const { data: plan, isLoading, isError } = useStudyPlan(planId);

  const markWatched = useMarkResourceWatched();
  const submitQuiz = useSubmitStudyPlanQuiz(planId);

  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({});
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
  const [isSubmittingQuiz, setIsSubmittingQuiz] = useState(false);

  const handleMarkWatched = (resourceId: string) => {
    if (!plan) return;
    markWatched.mutate({ planId: plan.id, resourceId });
  };

  const handleQuizSubmit = async () => {
    if (!plan) return;
    setIsSubmittingQuiz(true);
    const responses = Object.entries(quizAnswers).map(([index, answer]) => ({
      question_index: Number(index),
      answer,
    }));
    try {
      const result = await submitQuiz.mutateAsync({ responses });
      setQuizResult(result);
    } catch {
      // error surfaced via submitQuiz.isError
    } finally {
      setIsSubmittingQuiz(false);
    }
  };

  const allQuestionsAnswered =
    (plan?.quiz_questions.length ?? 0) > 0 &&
    Object.keys(quizAnswers).length === (plan?.quiz_questions.length ?? 0);

  const isCompleted = plan?.status === "COMPLETED";
  const canTakeQuiz =
    (plan?.status === "ACTIVE" || plan?.status === "IN_PROGRESS") &&
    (plan?.quiz_questions.length ?? 0) > 0 &&
    !quizResult;

  return (
    <StudentLayout
      activeNav="home"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      onLogout={layout.onLogout}
    >
      <div className="max-w-2xl mx-auto space-y-6">
        <button
          type="button"
          onClick={() => navigate("/student/study-plans")}
          className="flex items-center gap-1.5 text-brand-muted hover:text-brand-ink transition-colors font-sans text-sm min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Back to Study Plans
        </button>

        {isLoading ? (
          <StudyPlanDetailSkeleton />
        ) : isError || !plan ? (
          <div className="text-center py-12">
            <p className="font-sans text-sm text-brand-red mb-4">
              Could not load this study plan. Please try again.
            </p>
            <button
              type="button"
              onClick={() => navigate("/student/study-plans")}
              className="bg-brand-primary text-white px-5 py-2.5 rounded-full font-sans text-sm hover:bg-brand-dark transition-colors"
            >
              Back to Study Plans
            </button>
          </div>
        ) : plan.status === "GENERATING" ? (
          <div className="bg-white border border-brand-border rounded-card p-12 text-center">
            <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <h2 className="font-display font-bold text-xl text-brand-ink mb-2">
              Your plan is being prepared
            </h2>
            <p className="font-sans text-sm text-brand-muted">
              We're personalising this study plan for you. Check back shortly.
            </p>
          </div>
        ) : (
          <>
            <div>
              <h1 className="font-display font-bold text-2xl text-brand-ink">
                {plan.subtopic_name}
              </h1>
              {isCompleted && plan.quiz_score !== null && (
                <p className="font-sans text-sm text-brand-green mt-1 flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" aria-hidden="true" />
                  Completed · Quiz score: {Math.round(plan.quiz_score * 100)}%
                </p>
              )}
            </div>

            {plan.resources.length > 0 && (
              <section className="space-y-3">
                <h2 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-body">
                  Learn
                </h2>
                <div className="space-y-2">
                  {plan.resources.map((resource) => (
                    <ResourceRow
                      key={resource.resource_id}
                      resource={resource}
                      onMarkWatched={() =>
                        handleMarkWatched(resource.resource_id)
                      }
                      isMarkingWatched={markWatched.isPending}
                      isCompleted={isCompleted}
                    />
                  ))}
                </div>
              </section>
            )}

            {plan.quiz_questions.length > 0 && (
              <section className="space-y-4">
                <h2 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-body">
                  Check your understanding
                </h2>

                {(isCompleted || quizResult) && (
                  <QuizResultBanner
                    score={quizResult?.score ?? plan.quiz_score ?? 0}
                    correctCount={quizResult?.correct_count ?? 0}
                    totalQuestions={
                      quizResult?.total_questions ?? plan.quiz_questions.length
                    }
                  />
                )}

                {canTakeQuiz && (
                  <div className="space-y-4">
                    {plan.quiz_questions.map((q) => (
                      <QuizQuestion
                        key={q.question_index}
                        question={q}
                        selectedKey={quizAnswers[q.question_index] ?? null}
                        onSelect={(key) =>
                          setQuizAnswers((prev) => ({
                            ...prev,
                            [q.question_index]: key,
                          }))
                        }
                      />
                    ))}

                    {submitQuiz.isError && (
                      <p className="font-sans text-sm text-brand-red">
                        Something went wrong submitting your quiz. Please try
                        again.
                      </p>
                    )}

                    <button
                      type="button"
                      onClick={handleQuizSubmit}
                      disabled={!allQuestionsAnswered || isSubmittingQuiz}
                      className="w-full bg-brand-primary text-white px-6 py-3 rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                    >
                      {isSubmittingQuiz ? "Submitting…" : "Submit Quiz"}
                    </button>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </StudentLayout>
  );
}

interface ResourceRowProps {
  resource: StudyPlanResource;
  onMarkWatched: () => void;
  isMarkingWatched: boolean;
  isCompleted: boolean;
}

function ResourceRow({
  resource,
  onMarkWatched,
  isMarkingWatched,
  isCompleted,
}: ResourceRowProps) {
  const resourceTypeIcon: Record<string, string> = {
    VIDEO: "▶",
    ARTICLE: "📄",
    INTERACTIVE: "🎮",
  };
  const icon = resourceTypeIcon[resource.resource_type] ?? "📄";

  return (
    <div className="bg-white border border-role-student-border rounded-card p-3 flex items-center gap-3">
      <span className="text-brand-muted text-sm w-5 text-center flex-shrink-0">
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-sans font-semibold text-sm text-brand-ink truncate">
          {resource.title}
        </p>
        {resource.duration_minutes && (
          <p className="font-sans text-xs text-brand-muted">
            {resource.duration_minutes} min
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {resource.is_watched ? (
          <span className="font-sans text-xs font-semibold text-brand-green flex items-center gap-1">
            <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />
            Done
          </span>
        ) : !isCompleted ? (
          <button
            type="button"
            onClick={onMarkWatched}
            disabled={isMarkingWatched}
            className="font-sans text-xs font-semibold text-brand-muted hover:text-brand-ink transition-colors disabled:opacity-50 min-h-[44px] px-1"
          >
            Mark done
          </button>
        ) : null}
        <a
          href={resource.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-primary hover:text-brand-dark transition-colors min-h-[44px] flex items-center"
          aria-label={`Open ${resource.title} in new tab`}
        >
          <ExternalLink className="w-4 h-4" aria-hidden="true" />
        </a>
      </div>
    </div>
  );
}

interface QuizQuestionProps {
  question: StudyPlanQuizQuestion;
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

function QuizQuestion({ question, selectedKey, onSelect }: QuizQuestionProps) {
  return (
    <div className="space-y-3">
      <p className="font-sans text-sm text-brand-ink leading-relaxed">
        {question.question_index + 1}. {question.question_text}
      </p>
      <div className="space-y-2">
        {question.options.map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => onSelect(opt.key)}
            aria-pressed={selectedKey === opt.key}
            className={`w-full flex items-start gap-3 p-3 rounded-xl text-left transition-all min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
              selectedKey === opt.key
                ? "border-2 border-brand-primary bg-brand-primary/10"
                : "border border-role-student-border bg-white hover:border-brand-primary/40"
            }`}
          >
            <span
              className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-sans font-bold text-xs ${
                selectedKey === opt.key
                  ? "bg-brand-primary text-white"
                  : "bg-gray-100 text-brand-muted"
              }`}
              aria-hidden="true"
            >
              {opt.key.toUpperCase()}
            </span>
            <span className="font-sans text-sm leading-snug pt-0.5 text-brand-ink">
              {opt.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function QuizResultBanner({
  score,
  correctCount,
  totalQuestions,
}: {
  score: number;
  correctCount: number;
  totalQuestions: number;
}) {
  const pct = Math.round(score * 100);
  const passed = pct >= 70;
  return (
    <div
      className={`rounded-xl p-4 text-center ${
        passed
          ? "bg-brand-green-light border border-brand-mid"
          : "bg-brand-amber-light border border-brand-gold-mid"
      }`}
      role="status"
    >
      <p
        className={`font-display font-bold text-2xl ${passed ? "text-brand-green" : "text-brand-gold-dark"}`}
      >
        {pct}%
      </p>
      <p
        className={`font-sans text-sm mt-1 ${passed ? "text-brand-green" : "text-brand-gold-dark"}`}
      >
        {correctCount} of {totalQuestions} correct
        {passed ? " · Great work!" : " · Keep practising"}
      </p>
    </div>
  );
}

function StudyPlanDetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-7 w-48 bg-brand-border rounded-full" />
      <div className="space-y-3">
        <div className="h-3 w-16 bg-brand-border-soft rounded-full" />
        {[1, 2].map((i) => (
          <div
            key={i}
            className="bg-white border border-brand-border rounded-card p-3 flex items-center gap-3"
          >
            <div className="w-5 h-5 bg-brand-border rounded" />
            <div className="flex-1">
              <div className="h-3 w-40 bg-brand-border rounded-full mb-1" />
              <div className="h-2 w-16 bg-brand-border-soft rounded-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
