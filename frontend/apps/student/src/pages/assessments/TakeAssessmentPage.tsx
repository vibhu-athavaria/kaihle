/**
 * TakeAssessmentPage — renders an in-progress assessment by attemptId.
 *
 * Route: /student/assessments/:attemptId/take
 *
 * Design: DESIGN_SYSTEM.md §5.4 Student — green primary actions, Fraunces headings,
 *         Nunito body, mobile-first layout.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle, Clock, X } from "lucide-react";
import { StudentLayout, Modal, Skeleton } from "@kaihle/ui";
import {
  useAttempt,
  useSubmitResponse,
  useSubmitAttempt,
  type AttemptAnswer,
} from "../../hooks/useAttempt";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";

// ─────────────────────────────────────────────────────────────
//  Countdown timer hook
// ─────────────────────────────────────────────────────────────

/**
 * Returns remaining seconds based on a server-side startedAt timestamp and a
 * limit in minutes. Ticks every second. Returns null when the assessment is
 * untimed (limitMinutes === 0) or startedAt is not yet available.
 */
function useCountdown(
  startedAt: string | null,
  limitMinutes: number,
): number | null {
  const computeRemaining = useCallback(() => {
    if (!startedAt || limitMinutes === 0) return null;
    const deadline = new Date(startedAt).getTime() + limitMinutes * 60 * 1000;
    return Math.max(0, Math.floor((deadline - Date.now()) / 1000));
  }, [startedAt, limitMinutes]);

  const [seconds, setSeconds] = useState<number | null>(computeRemaining);

  useEffect(() => {
    if (!startedAt || limitMinutes === 0) return;
    // Sync immediately in case stale state from previous render
    setSeconds(computeRemaining());
    const id = setInterval(() => {
      setSeconds(computeRemaining());
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt, limitMinutes, computeRemaining]);

  return seconds;
}

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ─────────────────────────────────────────────────────────────
//  Save indicator
// ─────────────────────────────────────────────────────────────

type SaveState = "idle" | "saving" | "saved" | "error";

// ─────────────────────────────────────────────────────────────
//  MCQ option button
// ─────────────────────────────────────────────────────────────

interface MCQOptionProps {
  optionKey: string;
  text: string;
  selected: boolean;
  onSelect: () => void;
}

function MCQOption({ optionKey, text, selected, onSelect }: MCQOptionProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={[
        "w-full flex items-start gap-3 p-4 rounded-xl text-left transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
        "min-h-[44px]", // WCAG touch target
        selected
          ? "border-2 border-brand-primary bg-brand-primary/10 text-brand-ink"
          : "border border-role-student-border bg-white text-brand-ink hover:border-brand-primary/40 hover:bg-gray-50",
      ].join(" ")}
    >
      {/* Key badge */}
      <span
        className={[
          "flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center",
          "font-sans font-bold text-xs",
          selected
            ? "bg-brand-primary text-white"
            : "bg-gray-100 text-brand-muted",
        ].join(" ")}
        aria-hidden="true"
      >
        {optionKey}
      </span>
      <span className="font-sans text-sm leading-snug pt-0.5">{text}</span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
//  Question card skeleton
// ─────────────────────────────────────────────────────────────

function QuestionSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-5 w-2/3 rounded-full" />
      <Skeleton className="h-16 w-full rounded-xl" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Main component
// ─────────────────────────────────────────────────────────────

export function TakeAssessmentPage() {
  const { attemptId = "" } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();

  // ── Student layout data ─────────────────────────────────────
  const layout = useStudentLayoutProps();

  // ── Attempt data ────────────────────────────────────────────
  const { data: attempt, isLoading, isError } = useAttempt(attemptId);

  // ── Local state ──────────────────────────────────────────────
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [showTimesUpModal, setShowTimesUpModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const hasAutoSubmitted = useRef(false);
  // tracks when the current question was first shown — resets on navigation
  const questionOpenedAt = useRef<number>(Date.now());

  // ref to track if we've already redirected for COMPLETED attempts
  const hasRedirected = useRef(false);

  // ── Mutations ─────────────────────────────────────────────
  const submitResponseMutation = useSubmitResponse();
  const submitAttemptMutation = useSubmitAttempt();

  // Reset the per-question timer whenever the student moves to a new question
  useEffect(() => {
    questionOpenedAt.current = Date.now();
  }, [currentIndex]);

  // ── Countdown timer ─────────────────────────────────────────
  const secondsRemaining = useCountdown(
    attempt?.started_at ?? null,
    attempt?.time_limit_minutes ?? 0,
  );

  // ── Redirect if already COMPLETED ──────────────────────────
  useEffect(() => {
    if (attempt && attempt.status === "COMPLETED" && !hasRedirected.current) {
      hasRedirected.current = true;
      navigate(`/student/assessments/${attemptId}/results`, { replace: true });
    }
  }, [attempt, attemptId, navigate]);

  // ── Hydrate state from saved responses on load ─────────────────
  const hasHydrated = useRef(false);
  useEffect(() => {
    if (!attempt || attempt.responses.length === 0 || hasHydrated.current)
      return;
    hasHydrated.current = true;

    // Build answers map from saved responses
    const savedAnswers: Record<string, string> = {};
    for (const r of attempt.responses) {
      savedAnswers[r.question_id] = r.selected_key;
    }
    setAnswers(savedAnswers);

    // Find the first unanswered question to resume from
    const questions = attempt.questions;
    for (let i = 0; i < questions.length; i++) {
      if (!savedAnswers[questions[i].question_id]) {
        setCurrentIndex(i);
        return;
      }
    }
    // All questions answered — stay on last one (student can submit)
    setCurrentIndex(Math.min(attempt.num_questions, questions.length) - 1);
  }, [attempt]);

  // ── Derived values ───────────────────────────────────────────
  const questions = (attempt?.questions ?? []).slice(0, attempt?.num_questions);
  const currentQuestion = questions[currentIndex];
  const totalQuestions = attempt?.num_questions ?? questions.length;
  const answeredCount = Object.keys(answers).length;
  const isLastQuestion = currentIndex === totalQuestions - 1;
  const selectedKey = currentQuestion
    ? (answers[currentQuestion.question_id] ?? null)
    : null;

  // Progress: % of answered questions
  const progressPct =
    totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0;

  // ── Auto-save on Next click ──────────────────────────────────
  const saveCurrentAnswer = useCallback(
    async (questionId: string, key: string) => {
      const timeTakenMs = Date.now() - questionOpenedAt.current;
      setSaveState("saving");
      let attempts = 0;
      while (attempts < 2) {
        try {
          await submitResponseMutation.mutateAsync({
            attemptId,
            questionId,
            selectedKey: key,
            timeTakenMs,
          });
          setSaveState("saved");
          // Reset to idle after 2 s
          setTimeout(() => setSaveState("idle"), 2000);
          return;
        } catch {
          attempts++;
        }
      }
      // Both retries exhausted
      setSaveState("error");
      setTimeout(() => setSaveState("idle"), 4000);
    },
    [attemptId, submitResponseMutation],
  );

  // ── Handle option select ─────────────────────────────────────
  const handleSelect = useCallback(
    (key: string) => {
      if (!currentQuestion) return;
      setAnswers((prev) => ({
        ...prev,
        [currentQuestion.question_id]: key,
      }));
    },
    [currentQuestion],
  );

  // ── Navigation helpers ───────────────────────────────────────
  const goToNext = useCallback(async () => {
    if (!currentQuestion) return;
    const key = answers[currentQuestion.question_id];
    if (key) {
      await saveCurrentAnswer(currentQuestion.question_id, key);
    }
    setCurrentIndex((i) => Math.min(i + 1, totalQuestions - 1));
  }, [answers, currentQuestion, saveCurrentAnswer, totalQuestions]);

  const goToPrev = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

  // ── Timed-out auto-submit ────────────────────────────────────
  const doTimedOutSubmit = useCallback(async () => {
    if (hasAutoSubmitted.current) return;
    hasAutoSubmitted.current = true;
    setShowTimesUpModal(true);
    setIsSubmitting(true);
    const answersArray: AttemptAnswer[] = Object.entries(answers).map(
      ([question_id, selected_key]) => ({ question_id, selected_key }),
    );
    try {
      const result = await submitAttemptMutation.mutateAsync({
        attemptId,
        answers: answersArray,
        timed_out: true,
      });
      setIsSubmitting(false);
      // Modal stays open — student dismisses it, then navigates to results
      // Store result in sessionStorage so the modal "View results" button can pass it
      sessionStorage.setItem(
        `attempt_result_${attemptId}`,
        JSON.stringify(result),
      );
    } catch {
      hasAutoSubmitted.current = false;
      setIsSubmitting(false);
      setShowTimesUpModal(false);
    }
  }, [answers, attemptId, submitAttemptMutation]);

  // Fire auto-submit the moment the timer reaches 0
  useEffect(() => {
    if (
      secondsRemaining === 0 &&
      !hasAutoSubmitted.current &&
      attempt?.status !== "COMPLETED"
    ) {
      void doTimedOutSubmit();
    }
  }, [secondsRemaining, doTimedOutSubmit, attempt?.status]);

  // ── Submit flow ──────────────────────────────────────────────
  // doSubmit is declared FIRST so handleSubmitRequest can list it as a dep
  const doSubmit = useCallback(async () => {
    setShowSubmitModal(false);
    setIsSubmitting(true);
    const answersArray: AttemptAnswer[] = Object.entries(answers).map(
      ([question_id, selected_key]) => ({ question_id, selected_key }),
    );
    try {
      const result = await submitAttemptMutation.mutateAsync({
        attemptId,
        answers: answersArray,
      });
      navigate(`/student/assessments/${attemptId}/results`, {
        state: { result },
        replace: true,
      });
    } catch {
      setIsSubmitting(false);
      // Let user try again — don't crash the page
    }
  }, [answers, attemptId, navigate, submitAttemptMutation]);

  const handleSubmitRequest = useCallback(() => {
    const unanswered = totalQuestions - answeredCount;
    if (unanswered > 0) {
      setShowSubmitModal(true);
    } else {
      void doSubmit();
    }
  }, [answeredCount, totalQuestions, doSubmit]);

  // ── Back button ──────────────────────────────────────────────
  const handleBackArrow = useCallback(() => {
    setShowLeaveModal(true);
  }, []);

  const handleConfirmLeave = useCallback(() => {
    setShowLeaveModal(false);
    navigate(-1);
  }, [navigate]);

  // ─────────────────────────────────────────────────────────────
  //  Render states
  // ─────────────────────────────────────────────────────────────

  if (isError) {
    return (
      <StudentLayout
        activeNav="assessments"
        studentName={layout.studentName}
        gradeName={layout.gradeName}
        curriculumName={layout.curriculumName}
        classes={layout.sidebarClasses}
        assessmentBadge={layout.assessmentBadge}
        onLogout={layout.onLogout}
      >
        <div className="text-center py-12">
          <p className="text-brand-red font-sans text-sm">
            Failed to load this assessment. Please go back and try again.
          </p>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="mt-4 bg-brand-primary text-white px-5 py-2 rounded-full font-sans text-sm hover:bg-brand-dark transition-colors"
          >
            Go back
          </button>
        </div>
      </StudentLayout>
    );
  }

  return (
    <StudentLayout
      activeNav="assessments"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      assessmentBadge={layout.assessmentBadge}
      onLogout={layout.onLogout}
    >
      {/* ── Loading overlay for submit ─────────────────────── */}
      {isSubmitting && (
        <div
          className="fixed inset-0 z-50 bg-white/80 flex items-center justify-center"
          aria-live="polite"
          aria-label="Submitting your assessment"
        >
          <div className="text-center space-y-3">
            <div className="w-10 h-10 border-4 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="font-sans text-sm text-brand-body">Submitting…</p>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto space-y-5">
        {/* ── Top bar ─────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleBackArrow}
              aria-label="Leave assessment"
              className="flex items-center gap-1.5 text-brand-muted hover:text-brand-ink transition-colors font-sans text-sm min-h-[44px] min-w-[44px]"
            >
              <ArrowLeft className="w-4 h-4" aria-hidden="true" />
              <span className="sr-only sm:not-sr-only">Back</span>
            </button>
          </div>

          <h1 className="font-display font-bold text-lg text-brand-ink truncate px-2">
            {attempt?.title ?? "Assessment"}
          </h1>

          <div className="flex items-center gap-3">
            {/* Countdown timer badge — only shown for timed assessments */}
            {secondsRemaining !== null && (
              <span
                className={[
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-full font-sans text-sm font-semibold tabular-nums",
                  secondsRemaining <= 0
                    ? "bg-red-600 text-white"
                    : secondsRemaining <= attempt!.time_limit_minutes * 60 * 0.1
                      ? "bg-red-600 text-white animate-pulse"
                      : secondsRemaining <=
                          attempt!.time_limit_minutes * 60 * 0.2
                        ? "bg-amber-500 text-white"
                        : "bg-brand-primary text-white",
                ].join(" ")}
                aria-live="polite"
                aria-label={`Time remaining: ${formatCountdown(Math.max(0, secondsRemaining))}`}
              >
                <Clock className="w-3.5 h-3.5" aria-hidden="true" />
                {formatCountdown(Math.max(0, secondsRemaining))}
              </span>
            )}
            {/* Q X / total indicator */}
            {!isLoading && totalQuestions > 0 && (
              <span className="font-sans text-sm font-semibold text-brand-ink whitespace-nowrap">
                Q{currentIndex + 1}&nbsp;/&nbsp;{totalQuestions}
              </span>
            )}
            {/* Cancel button */}
            <button
              type="button"
              onClick={handleBackArrow}
              aria-label="Cancel assessment"
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-gray-100 text-brand-ink hover:bg-gray-200 font-sans text-sm font-medium transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              <X className="w-4 h-4" aria-hidden="true" />
              <span className="hidden sm:inline">Cancel</span>
            </button>
          </div>
        </div>

        {/* ── Progress bar ─────────────────────────────────── */}
        <div
          className="w-full bg-brand-border-soft rounded-full h-2"
          role="progressbar"
          aria-valuenow={Math.round(progressPct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${answeredCount} of ${totalQuestions} questions answered`}
        >
          <div
            className="bg-brand-primary h-2 rounded-full transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {/* ── Question card ─────────────────────────────────── */}
        {isLoading ? (
          <QuestionSkeleton />
        ) : currentQuestion ? (
          <div className="bg-white rounded-card border border-brand-border p-5 space-y-5 shadow-sm">
            {/* Meta row: question type + difficulty */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-green-pale text-brand-primary">
                {currentQuestion.question_type === "TRUE_FALSE"
                  ? "True / False"
                  : "Multiple choice"}
              </span>
              {currentQuestion.difficulty_level > 0 && (
                <span
                  className={[
                    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold",
                    currentQuestion.difficulty_level >= 4
                      ? "bg-red-50 text-red-700"
                      : currentQuestion.difficulty_level >= 2
                        ? "bg-amber-50 text-amber-700"
                        : "bg-gray-100 text-brand-body",
                  ].join(" ")}
                >
                  {currentQuestion.difficulty_level >= 4
                    ? "Hard"
                    : currentQuestion.difficulty_level >= 2
                      ? "Medium"
                      : "Easy"}
                </span>
              )}
              {currentQuestion.subtopic_name && (
                <span className="text-xs text-brand-muted truncate">
                  {currentQuestion.subtopic_name}
                </span>
              )}
            </div>

            {/* Question text */}
            <p className="font-sans text-base text-brand-ink leading-relaxed">
              {currentQuestion.question_text}
            </p>

            {/* Options: stacked for True/False, 2-col grid for MCQ */}
            <div
              className={
                currentQuestion.question_type === "TRUE_FALSE"
                  ? "flex flex-col gap-3"
                  : "grid grid-cols-1 sm:grid-cols-2 gap-3"
              }
              role="radiogroup"
              aria-label={`Options for question ${currentIndex + 1}`}
            >
              {currentQuestion.options.map((opt) => (
                <MCQOption
                  key={opt.key}
                  optionKey={opt.key}
                  text={opt.text}
                  selected={selectedKey === opt.key}
                  onSelect={() => handleSelect(opt.key)}
                />
              ))}
            </div>
          </div>
        ) : (
          <p className="font-sans text-sm text-brand-muted">
            No questions found for this assessment.
          </p>
        )}

        {/* ── Navigation buttons ────────────────────────────── */}
        {!isLoading && totalQuestions > 0 && (
          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={goToPrev}
              disabled={currentIndex === 0}
              className={[
                "flex items-center gap-1.5 px-5 py-2.5 rounded-full font-sans text-sm transition-colors min-h-[44px]",
                "border border-role-student-border",
                currentIndex === 0
                  ? "text-brand-muted cursor-not-allowed opacity-50"
                  : "text-brand-ink hover:bg-gray-50",
              ].join(" ")}
            >
              <ArrowLeft className="w-4 h-4" aria-hidden="true" />
              Back
            </button>

            {/* Save indicator — always rendered to avoid layout shift */}
            <p
              aria-live="polite"
              className={[
                "font-sans text-xs transition-opacity duration-200",
                saveState === "idle" ? "invisible" : "visible",
                saveState === "saving" && "text-brand-muted",
                saveState === "saved" && "text-brand-green",
                saveState === "error" && "text-brand-red",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {saveState === "saving" && "Saving…"}
              {saveState === "saved" && (
                <>
                  <CheckCircle
                    className="inline w-3 h-3 mr-0.5"
                    aria-hidden="true"
                  />
                  Saved
                </>
              )}
              {saveState === "error" && "Save failed"}
            </p>

            {isLastQuestion ? (
              <button
                type="button"
                onClick={handleSubmitRequest}
                className="flex items-center gap-1.5 bg-brand-primary text-white px-5 py-2.5 rounded-full font-sans text-sm hover:bg-brand-dark transition-colors min-h-[44px]"
              >
                Submit Assessment
              </button>
            ) : (
              <button
                type="button"
                onClick={goToNext}
                disabled={!selectedKey}
                className="flex items-center gap-1.5 bg-brand-primary text-white px-5 py-2.5 rounded-full font-sans text-sm hover:bg-brand-dark transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Leave confirmation modal ─────────────────────────── */}
      <Modal
        open={showLeaveModal}
        onOpenChange={setShowLeaveModal}
        title="Leave this assessment?"
        maxWidth="sm"
      >
        <p className="font-sans text-sm text-brand-body mb-5">
          Your progress will be saved. You can resume this assessment later.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={() => setShowLeaveModal(false)}
            className="px-4 py-2 rounded-full border border-role-student-border text-brand-ink font-sans text-sm hover:bg-gray-50 min-h-[44px] transition-colors"
          >
            Keep going
          </button>
          <button
            type="button"
            onClick={handleConfirmLeave}
            className="px-4 py-2 rounded-full bg-brand-primary text-white font-sans text-sm hover:bg-brand-dark min-h-[44px] transition-colors"
          >
            Leave
          </button>
        </div>
      </Modal>

      {/* ── Unanswered questions modal ───────────────────────── */}
      <Modal
        open={showSubmitModal}
        onOpenChange={setShowSubmitModal}
        title="Some questions unanswered"
        maxWidth="sm"
      >
        <p className="font-sans text-sm text-brand-body mb-5">
          You have left <strong>{totalQuestions - answeredCount}</strong>{" "}
          question
          {totalQuestions - answeredCount !== 1 ? "s" : ""} unanswered.
          Unanswered questions will count as incorrect. Submit anyway?
        </p>
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={() => setShowSubmitModal(false)}
            className="px-4 py-2 rounded-full border border-role-student-border text-brand-ink font-sans text-sm hover:bg-gray-50 min-h-[44px] transition-colors"
          >
            Go back
          </button>
          <button
            type="button"
            onClick={() => void doSubmit()}
            className="px-4 py-2 rounded-full bg-brand-primary text-white font-sans text-sm hover:bg-brand-dark min-h-[44px] transition-colors"
          >
            Submit anyway
          </button>
        </div>
      </Modal>

      {/* ── Time's up modal ──────────────────────────────────── */}
      <Modal
        open={showTimesUpModal}
        onOpenChange={() => {}}
        title="Time's up!"
        maxWidth="sm"
      >
        <p className="font-sans text-sm text-brand-body mb-5">
          Your time has run out. Any unanswered questions have been marked as
          incorrect. Your results are ready to view.
        </p>
        <div className="flex justify-end">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() =>
              navigate(`/student/assessments/${attemptId}/results`, {
                replace: true,
              })
            }
            className="px-5 py-2 rounded-full bg-brand-primary text-white font-sans text-sm hover:bg-brand-dark min-h-[44px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? "Submitting…" : "View results"}
          </button>
        </div>
      </Modal>
    </StudentLayout>
  );
}
