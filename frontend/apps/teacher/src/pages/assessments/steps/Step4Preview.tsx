import { useEffect, useState } from "react";
import { apiClient } from "@kaihle/auth";
import { Button, Badge, Skeleton } from "@kaihle/ui";
import { X } from "lucide-react";
import {
  useAssessmentWizard,
  type PreviewQuestion,
} from "../../../hooks/useAssessmentWizard";

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

  const [localQuestions, setLocalQuestions] = useState<PreviewQuestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [insufficientError, setInsufficientError] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    // If we already have a draft from a previous visit to this step, use it
    if (draftAssessmentId && previewQuestions.length > 0) {
      setLocalQuestions(previewQuestions);
      return;
    }

    if (!classId) return;

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
        );

        const questions: PreviewQuestion[] = (res.data.questions ?? []).map(
          (q: {
            id?: string;
            question_id?: string;
            question_text: string;
            options: Array<{ key: string; text: string }>;
          }) => ({
            question_id: q.id ?? q.question_id ?? "",
            question_text: q.question_text,
            options: q.options ?? [],
          }),
        );

        setDraftAssessment(res.data.id, questions);
        setLocalQuestions(questions);
      } catch (err: unknown) {
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
        setIsLoading(false);
      }
    }

    void createDraft();
    // We intentionally only run this on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function removeQuestion(questionId: string) {
    setLocalQuestions((prev) =>
      prev.filter((q) => q.question_id !== questionId),
    );
  }

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
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    );
  }

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm font-sans text-brand-muted">
          {localQuestions.length} question
          {localQuestions.length !== 1 ? "s" : ""} selected
        </p>
        <Badge variant="info">Preview</Badge>
      </div>

      <div className="space-y-3">
        {localQuestions.map((q, idx) => (
          <div
            key={q.question_id}
            className="bg-white border border-brand-border rounded-xl p-4 flex gap-3"
          >
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-light text-brand-primary text-xs font-bold font-sans flex items-center justify-center">
              {idx + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-sans text-brand-ink leading-relaxed">
                  {q.question_text}
                </p>
                <button
                  type="button"
                  onClick={() => removeQuestion(q.question_id)}
                  className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-brand-muted hover:text-brand-red hover:bg-brand-red-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                  aria-label={`Remove question ${idx + 1}`}
                >
                  <X className="w-3 h-3" aria-hidden="true" />
                </button>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Badge variant="neutral">MCQ</Badge>
                {q.options.length > 0 && (
                  <span className="text-xs font-sans text-brand-muted">
                    {q.options.length} options
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {localQuestions.length === 0 && !isLoading && !insufficientError && (
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
          Review & Publish
        </Button>
      </div>
    </div>
  );
}
