import { useEffect, useState } from "react";
import { apiClient } from "@kaihle/auth";
import { Button, Badge, Skeleton, Modal } from "@kaihle/ui";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
import {
  useAssessmentWizard,
  type PreviewQuestion,
} from "../../../hooks/useAssessmentWizard";

const PAGE_SIZE = 3;

export function Step4Preview() {
  const {
    classId,
    assessmentType,
    topicIds,
    questionCount,
    difficultyMin,
    difficultyMax,
    deadline,
    draftAssessmentId,
    previewQuestions,
    setDraftAssessment,
    setStep,
  } = useAssessmentWizard();

  const [localQuestions, setLocalQuestions] = useState<PreviewQuestion[]>(
    draftAssessmentId && previewQuestions.length > 0 ? previewQuestions : [],
  );
  const [isLoading, setIsLoading] = useState(false);
  const [insufficientError, setInsufficientError] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [attemptOpen, setAttemptOpen] = useState(false);
  const [attemptIndex, setAttemptIndex] = useState(0);
  const [attemptAnswers, setAttemptAnswers] = useState<Record<string, string>>(
    {},
  );
  const [attemptDone, setAttemptDone] = useState(false);

  useEffect(() => {
    if (draftAssessmentId && previewQuestions.length > 0) return;
    if (!classId) return;

    const abortController = new AbortController();

    async function createDraft() {
      setIsLoading(true);
      setInsufficientError(false);
      setServerError(null);

      try {
        const payload: Record<string, unknown> = {
          assessment_type: assessmentType,
          question_count: questionCount,
          difficulty_min: difficultyMin,
          difficulty_max: difficultyMax,
          topic_ids: topicIds.length > 0 ? topicIds : undefined,
          deadline: deadline ?? undefined,
          is_system_generated: false,
        };

        const res = await apiClient.post(
          `/api/v1/classes/${classId}/assessments`,
          payload,
          { signal: abortController.signal },
        );

        if (abortController.signal.aborted) return;

        const questions: PreviewQuestion[] = (res.data.questions ?? []).map(
          (q: {
            id?: string;
            question_id?: string;
            question_text: string;
            options: Array<{ key: string; text: string }>;
            difficulty_level: number;
            subtopic_name: string;
          }) => ({
            question_id: q.id ?? q.question_id ?? "",
            question_text: q.question_text,
            options: q.options ?? [],
            difficulty_level: q.difficulty_level ?? 1,
            subtopic_name: q.subtopic_name ?? "Unknown",
          }),
        );

        setDraftAssessment(res.data.id, questions);
        setLocalQuestions(questions);
      } catch (err: unknown) {
        if (abortController.signal.aborted) return;
        const axiosErr = err as {
          response?: { status?: number; data?: { detail?: string } };
        };
        if (axiosErr?.response?.status === 422) {
          setInsufficientError(true);
        } else {
          setServerError(
            axiosErr?.response?.data?.detail ??
              "An unexpected error occurred. Please try again.",
          );
        }
      } finally {
        if (!abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void createDraft();
    return () => {
      abortController.abort();
    };
    // We intentionally only run this on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openAttempt(startIndex = 0) {
    setAttemptIndex(startIndex);
    setAttemptAnswers({});
    setAttemptDone(false);
    setAttemptOpen(true);
  }

  function removeQuestion(questionId: string) {
    setLocalQuestions((prev) =>
      prev.filter((q) => q.question_id !== questionId),
    );
    setCurrentPage(1);
  }

  // ── Loading state ────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 mb-4">
          <span
            className="w-4 h-4 border-2 border-brand-gold border-t-transparent rounded-full animate-spin"
            aria-hidden="true"
          />
          <p className="text-sm font-sans text-brand-body italic">
            Selecting questions from the bank…
          </p>
        </div>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  // ── Error states ─────────────────────────────────────────────────────────
  if (insufficientError) {
    return (
      <div className="space-y-6">
        <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
          <p className="text-sm font-sans font-semibold text-brand-red mb-1">
            Not enough questions
          </p>
          <p className="text-sm font-sans text-brand-red">
            Not enough questions in the bank for this configuration. Try
            broadening your topic selection or difficulty range.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setStep(3)}>
          Back to Configuration
        </Button>
      </div>
    );
  }

  if (serverError) {
    return (
      <div className="space-y-6">
        <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
          <p className="text-sm font-sans font-semibold text-brand-red mb-1">
            Something went wrong
          </p>
          <p className="text-sm font-sans text-brand-red">{serverError}</p>
        </div>
        <Button variant="secondary" onClick={() => setStep(3)}>
          Back to Configuration
        </Button>
      </div>
    );
  }

  // ── Computed values ───────────────────────────────────────────────────────
  const difficultyMap = localQuestions.reduce<Record<number, number>>(
    (acc, q) => {
      acc[q.difficulty_level] = (acc[q.difficulty_level] ?? 0) + 1;
      return acc;
    },
    {},
  );
  const difficultyLevels = Object.keys(difficultyMap)
    .map(Number)
    .sort((a, b) => a - b);
  const maxCount =
    difficultyLevels.length > 0 ? Math.max(...Object.values(difficultyMap)) : 1;
  const topicCount = new Set(localQuestions.map((q) => q.subtopic_name)).size;
  const diffMin =
    difficultyLevels.length > 0 ? Math.min(...difficultyLevels) : difficultyMin;
  const diffMax =
    difficultyLevels.length > 0 ? Math.max(...difficultyLevels) : difficultyMax;

  const totalPages = Math.max(1, Math.ceil(localQuestions.length / PAGE_SIZE));
  const pageQuestions = localQuestions.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  // ── Main render ───────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">
      {/* Stats bar */}
      <div className="space-y-2">
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-brand-light border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-primary leading-none">
              {localQuestions.length}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">in pool</p>
          </div>
          <div className="bg-[#fffbeb] border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-gold leading-none">
              {questionCount}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">
              per attempt
            </p>
          </div>
          <div className="bg-white border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-ink leading-none">
              {topicCount}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">subtopics</p>
          </div>
          <div className="bg-white border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-ink leading-none">
              {diffMin}–{diffMax}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">
              difficulty
            </p>
          </div>
        </div>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => openAttempt(0)}
            disabled={localQuestions.length === 0}
            className="text-xs font-sans font-bold text-brand-gold border border-[#fde68a] bg-[#fffbeb] rounded-full px-4 py-1.5 hover:bg-[#fef3c7] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          >
            Try assessment →
          </button>
        </div>
      </div>

      {/* Difficulty distribution chart */}
      {difficultyLevels.length > 0 && (
        <div className="bg-white border border-brand-border rounded-xl p-4">
          <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted mb-3">
            Difficulty distribution
          </p>
          <div className="flex items-end gap-2 h-10">
            {difficultyLevels.map((level) => {
              const count = difficultyMap[level] ?? 0;
              const heightPct = Math.round((count / maxCount) * 100);
              const isHigher = level > 3;
              return (
                <div
                  key={level}
                  className="flex-1 flex flex-col items-center gap-1"
                >
                  <div
                    className="w-full rounded-t"
                    style={{
                      height: `${heightPct}%`,
                      minHeight: "4px",
                      background: isHigher ? "#c9932a" : "#1a5c38",
                      opacity: 0.5 + level * 0.08,
                    }}
                    aria-label={`Level ${level}: ${count} questions`}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex gap-2 mt-2">
            {difficultyLevels.map((level) => (
              <div key={level} className="flex-1 text-center">
                <p className="text-[10px] font-sans text-brand-muted">
                  Lvl {level}
                </p>
                <p className="text-[10px] font-sans font-bold text-brand-ink">
                  {difficultyMap[level] ?? 0}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Question list header */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted">
          Questions in pool
        </p>
        <p className="text-xs font-sans text-brand-muted">
          {localQuestions.length} total
        </p>
      </div>

      {/* Question rows */}
      <div className="space-y-2">
        {pageQuestions.map((q, idx) => {
          const globalIdx = (currentPage - 1) * PAGE_SIZE + idx + 1;
          return (
            <div
              key={q.question_id}
              className="bg-white border border-brand-border rounded-xl p-3 flex items-center gap-3"
            >
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-light text-brand-primary text-xs font-bold font-sans flex items-center justify-center">
                {globalIdx}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-sans text-brand-ink truncate font-medium">
                  {q.question_text}
                </p>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <Badge variant="neutral">
                    {"⭐".repeat(Math.min(q.difficulty_level, 5))} Lvl{" "}
                    {q.difficulty_level}
                  </Badge>
                  <Badge variant="info">{q.subtopic_name}</Badge>
                  <span className="text-xs font-sans text-brand-muted">
                    {q.options.length} options
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  type="button"
                  onClick={() =>
                    openAttempt((currentPage - 1) * PAGE_SIZE + idx)
                  }
                  className="text-xs font-sans font-bold text-brand-gold bg-[#fffbeb] border border-[#fde68a] rounded-md px-2 py-1 hover:bg-[#fef3c7] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                >
                  Try
                </button>
                <button
                  type="button"
                  onClick={() => removeQuestion(q.question_id)}
                  className="w-6 h-6 rounded-full flex items-center justify-center text-brand-muted hover:text-brand-red hover:bg-brand-red-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                  aria-label={`Remove question ${globalIdx}`}
                >
                  <X className="w-3 h-3" aria-hidden="true" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="border border-brand-border rounded-lg p-1.5 text-brand-body hover:text-brand-ink disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
          </button>
          <span className="text-xs font-sans text-brand-body">
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="border border-brand-border rounded-lg p-1.5 text-brand-body hover:text-brand-ink disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
            aria-label="Next page"
          >
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Empty state */}
      {localQuestions.length === 0 && (
        <p className="text-sm font-sans text-brand-muted text-center py-8">
          All questions have been removed. Go back to select a different
          configuration.
        </p>
      )}

      {/* Footer */}
      <div className="flex justify-between pt-2">
        <Button variant="secondary" onClick={() => setStep(3)}>
          Back
        </Button>
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          disabled={localQuestions.length === 0}
          onClick={() => setStep(5)}
        >
          Review &amp; Publish
        </Button>
      </div>

      {/* Attempt-mode modal */}
      <Modal
        open={attemptOpen}
        onOpenChange={(open) => {
          if (!open) setAttemptOpen(false);
        }}
        title="Try assessment"
        description="Preview only — no answers are stored."
      >
        {(() => {
          const currentQ = localQuestions[attemptIndex];
          const totalQ = localQuestions.length;
          const progressPct =
            totalQ > 0 ? Math.round((attemptIndex / totalQ) * 100) : 0;
          const selectedKey = currentQ
            ? attemptAnswers[currentQ.question_id]
            : undefined;
          const answered = selectedKey !== undefined;

          if (attemptDone) {
            return (
              <div className="space-y-6 text-center py-4">
                <p className="font-display font-bold text-2xl text-brand-ink">
                  You attempted all {totalQ} questions
                </p>
                <p className="text-sm font-sans text-brand-body">
                  This was a preview — no answers were stored.
                </p>
                <button
                  type="button"
                  onClick={() => setAttemptOpen(false)}
                  className="px-6 py-2 bg-brand-primary text-white rounded-full text-sm font-sans font-bold hover:bg-brand-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                >
                  Close
                </button>
              </div>
            );
          }

          if (!currentQ) return null;

          return (
            <div className="space-y-5">
              {/* Progress */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-sans font-bold uppercase tracking-wide text-brand-muted">
                    Question {attemptIndex + 1} of {totalQ}
                  </span>
                  <span className="text-xs font-sans text-brand-muted">
                    {"●".repeat(Math.min(currentQ.difficulty_level, 5))}
                    {"○".repeat(
                      Math.max(0, 5 - currentQ.difficulty_level),
                    )} Lvl {currentQ.difficulty_level}
                  </span>
                </div>
                <div className="w-full bg-brand-border rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-brand-primary h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                    role="progressbar"
                    aria-valuenow={progressPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                </div>
              </div>

              {/* Question text */}
              <p className="text-sm font-sans font-semibold text-brand-ink leading-relaxed">
                {currentQ.question_text}
              </p>

              {/* Options */}
              <div className="space-y-2">
                {currentQ.options.map((opt) => {
                  const isSelected = selectedKey === opt.key;
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      disabled={answered}
                      onClick={() =>
                        setAttemptAnswers((prev) => ({
                          ...prev,
                          [currentQ.question_id]: opt.key,
                        }))
                      }
                      className={[
                        "w-full text-left flex items-center gap-3 px-4 py-2.5 rounded-xl border-[1.5px] transition-colors text-sm font-sans",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1",
                        answered && !isSelected
                          ? "border-brand-border text-brand-muted cursor-default opacity-60"
                          : isSelected
                            ? "border-brand-primary bg-brand-light text-brand-primary font-semibold"
                            : "border-brand-border text-brand-ink hover:border-brand-primary hover:bg-brand-light cursor-pointer",
                      ].join(" ")}
                    >
                      <span
                        className={[
                          "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0",
                          isSelected
                            ? "bg-brand-primary text-white"
                            : "bg-brand-border-soft text-brand-muted",
                        ].join(" ")}
                      >
                        {opt.key.toUpperCase()}
                      </span>
                      <span>{opt.text}</span>
                      {isSelected && (
                        <span className="ml-auto text-xs font-bold text-brand-primary">
                          ✓ Selected
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Footer note */}
              <p className="text-xs font-sans text-brand-muted text-center italic">
                Preview only — no answers stored
              </p>

              {/* Navigation */}
              <div className="flex justify-between pt-1">
                <button
                  type="button"
                  disabled={attemptIndex === 0}
                  onClick={() => setAttemptIndex((i) => i - 1)}
                  className="px-4 py-2 border border-brand-border rounded-full text-xs font-sans font-semibold text-brand-body hover:text-brand-ink disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
                >
                  ← Previous
                </button>
                {answered &&
                  (attemptIndex < totalQ - 1 ? (
                    <button
                      type="button"
                      onClick={() => setAttemptIndex((i) => i + 1)}
                      className="px-4 py-2 bg-brand-primary text-white rounded-full text-xs font-sans font-bold hover:bg-brand-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
                    >
                      Next →
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setAttemptDone(true)}
                      className="px-4 py-2 bg-brand-primary text-white rounded-full text-xs font-sans font-bold hover:bg-brand-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
                    >
                      See results →
                    </button>
                  ))}
              </div>
            </div>
          );
        })()}
      </Modal>
    </div>
  );
}
