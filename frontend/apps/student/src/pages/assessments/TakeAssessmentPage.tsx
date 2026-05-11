/**
 * TakeAssessmentPage — used for both Tier 1 (onboarding diagnostic) and
 * Tier 2 (teacher-created progress check) assessments.
 *
 * Route: /student/assessments/:attemptId/take
 *
 * Design: DESIGN_SYSTEM.md §5.4 Student — green primary actions, Fraunces headings,
 *         Nunito body, mobile-first layout.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle, X } from "lucide-react";
import { StudentLayout, Modal, Skeleton } from "@kaihle/ui";
import {
  useAttempt,
  useSubmitResponse,
  useSubmitAttempt,
  type AttemptAnswer,
} from "../../hooks/useAttempt";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";

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
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ref to track if we've already redirected for COMPLETED attempts
  const hasRedirected = useRef(false);

  // ── Mutations ─────────────────────────────────────────────
  const submitResponseMutation = useSubmitResponse();
  const submitAttemptMutation = useSubmitAttempt();

  // ── Redirect if already COMPLETED ──────────────────────────
  useEffect(() => {
    if (attempt && attempt.status === "COMPLETED" && !hasRedirected.current) {
      hasRedirected.current = true;
      navigate(`/student/assessments/${attemptId}/results`, { replace: true });
    }
  }, [attempt, attemptId, navigate]);

  // ── Derived values ───────────────────────────────────────────
  const questions = attempt?.questions ?? [];
  const currentQuestion = questions[currentIndex];
  const totalQuestions = questions.length;
  const answeredCount = Object.keys(answers).length;
  const isLastQuestion = currentIndex === totalQuestions - 1;
  const selectedKey = currentQuestion
    ? (answers[currentQuestion.question_id] ?? null)
    : null;

  // Progress: % of answered questions
  const progressPct =
    totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0;

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

  // ── Auto-save on Next click ──────────────────────────────────
  const saveCurrentAnswer = useCallback(
    async (questionId: string, key: string) => {
      setSaveState("saving");
      let attempts = 0;
      while (attempts < 2) {
        try {
          await submitResponseMutation.mutateAsync({
            attemptId,
            questionId,
            selectedKey: key,
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

  // ── Navigation helpers ───────────────────────────────────────
  const goToNext = useCallback(async () => {
    if (!currentQuestion) return;
    const key = answers[currentQuestion.question_id];
    if (key) {
      // fire-and-forget save; don't block navigation
      void saveCurrentAnswer(currentQuestion.question_id, key);
    }
    setCurrentIndex((i) => Math.min(i + 1, totalQuestions - 1));
  }, [answers, currentQuestion, saveCurrentAnswer, totalQuestions]);

  const goToPrev = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

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
            {/* Q X / total indicator */}
            {!isLoading && totalQuestions > 0 && (
              <span className="font-sans text-sm text-brand-muted whitespace-nowrap">
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
        <div className="space-y-1">
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

          {/* Save indicator */}
          {saveState !== "idle" && (
            <p
              aria-live="polite"
              className={[
                "font-sans text-xs",
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
                  Saved ✓
                </>
              )}
              {saveState === "error" && "Save failed — check your connection"}
            </p>
          )}
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
                className="flex items-center gap-1.5 bg-brand-primary text-white px-5 py-2.5 rounded-full font-sans text-sm hover:bg-brand-dark transition-colors min-h-[44px]"
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
    </StudentLayout>
  );
}
