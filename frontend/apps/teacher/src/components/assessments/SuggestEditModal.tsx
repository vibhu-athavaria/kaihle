import { useState, useEffect, useRef } from "react";
import { Modal, Button } from "@kaihle/ui";
import { useSuggestEdit } from "../../hooks/useAssessmentQuestions";
import type { PreviewQuestion } from "../../hooks/useAssessmentPreview";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessmentId: string;
  question: PreviewQuestion | null;
  onSuccess?: () => void;
}

export function SuggestEditModal({
  open,
  onOpenChange,
  assessmentId,
  question,
  onSuccess,
}: Props) {
  const [questionText, setQuestionText] = useState("");
  const [correctAnswer, setCorrectAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [difficultyLevel, setDifficultyLevel] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const suggestMutation = useSuggestEdit(assessmentId);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (open && question) {
      setQuestionText(question.question_text);
      setCorrectAnswer(question.correct_answer_key);
      setExplanation(question.explanation ?? "");
      setDifficultyLevel(question.difficulty_level);
      setReason("");
      setSuccessMsg(null);
      setErrorMsg(null);
    }
    // Cleanup timeout on unmount or when open/closed
    return () => {
      if (closeTimeoutRef.current) {
        clearTimeout(closeTimeoutRef.current);
        closeTimeoutRef.current = null;
      }
    };
  }, [open, question]);

  if (!question) return null;

  async function handleSubmit() {
    if (!reason.trim()) {
      setErrorMsg("Please explain why you are suggesting this edit.");
      return;
    }
    setErrorMsg(null);

    const payload: Record<string, unknown> = { reason: reason.trim() };
    if (questionText !== question!.question_text)
      payload.suggested_question_text = questionText;
    if (correctAnswer !== question!.correct_answer_key)
      payload.suggested_correct_answer = correctAnswer;
    if (explanation !== (question!.explanation ?? ""))
      payload.suggested_explanation = explanation || null;
    if (difficultyLevel !== question!.difficulty_level)
      payload.suggested_difficulty_level = difficultyLevel;

    if (Object.keys(payload).length === 1) {
      setErrorMsg("No changes detected. Please edit at least one field.");
      return;
    }

    try {
      await suggestMutation.mutateAsync({
        questionId: question!.question_id,
        payload: payload as unknown as Parameters<
          typeof suggestMutation.mutateAsync
        >[0]["payload"],
      });
      setSuccessMsg("Suggestion submitted for KaihleAdmin review.");
      onSuccess?.();
      closeTimeoutRef.current = setTimeout(() => onOpenChange(false), 1500);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to submit suggestion.";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Suggest Question Edit"
    >
      <div className="space-y-4">
        <p className="text-xs font-sans text-brand-body leading-relaxed">
          Your suggestion will be reviewed by KaihleAdmin. The question bank
          won't change until the suggestion is approved.
        </p>

        {/* Original (read-only reference) */}
        <div className="bg-brand-border-soft border border-brand-border rounded-xl p-3">
          <p className="text-[10px] font-sans font-bold uppercase tracking-widest text-brand-muted mb-1">
            Current question
          </p>
          <p className="text-xs font-sans text-brand-body">
            {question.question_text}
          </p>
        </div>

        {/* Suggested question text */}
        <div>
          <label
            htmlFor="suggest-text"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Suggested question text
          </label>
          <textarea
            id="suggest-text"
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            rows={3}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          />
        </div>

        {/* Correct answer */}
        <div>
          <label
            htmlFor="suggest-answer"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Correct answer
          </label>
          <input
            id="suggest-answer"
            type="text"
            value={correctAnswer}
            onChange={(e) => setCorrectAnswer(e.target.value)}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          />
        </div>

        {/* Explanation */}
        <div>
          <label
            htmlFor="suggest-explanation"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Explanation{" "}
            <span className="font-normal text-brand-muted">(optional)</span>
          </label>
          <textarea
            id="suggest-explanation"
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            rows={2}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          />
        </div>

        {/* Difficulty */}
        <div>
          <label className="block text-xs font-sans font-semibold text-brand-ink mb-1.5">
            Difficulty:{" "}
            <span className="text-brand-gold-dark">
              {"⭐".repeat(difficultyLevel ?? question.difficulty_level)}
            </span>
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={difficultyLevel ?? question.difficulty_level}
            onChange={(e) => setDifficultyLevel(parseInt(e.target.value, 10))}
            className="w-full accent-brand-gold"
          />
        </div>

        {/* Reason (required) */}
        <div>
          <label
            htmlFor="suggest-reason"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Reason <span className="text-brand-red">*</span>
          </label>
          <textarea
            id="suggest-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            placeholder="e.g. The answer key is incorrect, there is a typo in option B…"
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          />
        </div>

        {successMsg && (
          <div className="bg-brand-green-light border border-brand-green/30 rounded-xl p-3">
            <p className="text-xs font-sans text-brand-green font-semibold">
              {successMsg}
            </p>
          </div>
        )}
        {errorMsg && (
          <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-3">
            <p className="text-xs font-sans text-brand-red">{errorMsg}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
            onClick={() => void handleSubmit()}
            disabled={suggestMutation.isPending}
          >
            {suggestMutation.isPending ? "Submitting…" : "Submit Suggestion"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
