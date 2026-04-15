import { useState } from "react";
import { X } from "lucide-react";
import { useConceptGuide, useMcqAnswer } from "../../hooks/useConceptGuide";

interface ConceptGuidePanelProps {
  subtopicId: string;
  subtopicName: string;
  onClose: () => void;
}

export function ConceptGuidePanel({
  subtopicId,
  subtopicName,
  onClose,
}: ConceptGuidePanelProps) {
  const [question, setQuestion] = useState("");
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const {
    mutate: generateGuide,
    isPending: isGenerating,
    data: guideData,
    error: guideError,
    reset: resetGuide,
  } = useConceptGuide();

  const {
    mutate: submitAnswer,
    isPending: isEvaluating,
    data: answerData,
    error: answerError,
    reset: resetAnswer,
  } = useMcqAnswer();

  const handleGenerate = () => {
    resetGuide();
    resetAnswer();
    setSelectedOption(null);
    generateGuide({ subtopicId, question: question.trim() || undefined });
  };

  const handleSelectOption = (option: string) => {
    if (answerData || isEvaluating) return;
    setSelectedOption(option);
  };

  const handleSubmitAnswer = () => {
    if (!selectedOption || !guideData?.checkQuestion) return;
    // Extract the letter prefix (e.g. "A" from "A) ...")
    const letter = selectedOption.charAt(0);
    submitAnswer({
      subtopicName: guideData.subtopicName,
      question: guideData.checkQuestion.question,
      options: guideData.checkQuestion.options,
      correct: guideData.checkQuestion.correct,
      studentAnswer: letter,
    });
  };

  const handleReset = () => {
    resetGuide();
    resetAnswer();
    setQuestion("");
    setSelectedOption(null);
  };

  return (
    <div
      className="mt-2 rounded-xl border border-brand-primary/20 bg-brand-light p-4"
      role="region"
      aria-label={`AI concept guide for ${subtopicName}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="font-sans text-xs font-bold uppercase tracking-widest text-brand-primary">
            AI Concept Guide
          </span>
          <p className="font-sans text-sm text-brand-ink mt-0.5">
            {subtopicName}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          aria-label="Close concept guide"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      {/* Optional question input — only before generating */}
      {!guideData && (
        <div className="mb-3">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a specific question (optional)"
            maxLength={500}
            className="w-full rounded-lg border border-brand-border px-3 py-2 text-sm font-sans transition-colors focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none bg-white"
            aria-label="Optional question about this concept"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !isGenerating) handleGenerate();
            }}
          />
        </div>
      )}

      {/* Generate button */}
      {!guideData && (
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating}
          className="w-full bg-brand-primary text-white rounded-full py-2 px-4 text-sm font-sans font-medium disabled:opacity-60 disabled:cursor-not-allowed min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 transition-colors"
        >
          {isGenerating ? (
            <span className="flex items-center justify-center gap-2">
              <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
              <span className="animate-pulse">Generating explanation...</span>
            </span>
          ) : (
            "Explain this concept"
          )}
        </button>
      )}

      {/* Guide error */}
      {guideError && (
        <div className="mt-2 text-brand-red text-xs font-sans">
          Something went wrong loading the guide. Please try again.
          <button
            type="button"
            onClick={handleGenerate}
            className="ml-2 underline text-brand-primary"
          >
            Retry
          </button>
        </div>
      )}

      {/* Explanation + MCQ */}
      {guideData && (
        <div className="space-y-4">
          <p className="font-sans text-sm text-brand-ink leading-relaxed">
            {guideData.explanation}
          </p>

          {/* MCQ check question — shown before answer is submitted */}
          {guideData.checkQuestion && !answerData && (
            <div className="space-y-2">
              <p className="font-sans text-sm font-semibold text-brand-ink">
                {guideData.checkQuestion.question}
              </p>
              <div className="space-y-2">
                {guideData.checkQuestion.options.map((option) => {
                  const isSelected = selectedOption === option;
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => handleSelectOption(option)}
                      disabled={isEvaluating}
                      className={`w-full text-left rounded-lg border px-3 py-2 text-sm font-sans transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
                        isSelected
                          ? "border-brand-primary bg-brand-light text-brand-primary font-medium"
                          : "border-brand-border bg-white text-brand-ink hover:border-brand-primary/50"
                      }`}
                    >
                      {option}
                    </button>
                  );
                })}
              </div>
              {selectedOption && (
                <button
                  type="button"
                  onClick={handleSubmitAnswer}
                  disabled={isEvaluating}
                  className="w-full bg-brand-primary text-white rounded-full py-2 px-4 text-sm font-sans font-medium disabled:opacity-60 min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 transition-colors mt-1"
                >
                  {isEvaluating ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      <span className="animate-pulse">Checking...</span>
                    </span>
                  ) : (
                    "Submit answer"
                  )}
                </button>
              )}
              {answerError && (
                <p className="text-brand-red text-xs font-sans">
                  Failed to check your answer. Please try again.
                </p>
              )}
            </div>
          )}

          {/* Follow-up response after MCQ answer */}
          {answerData && (
            <div
              className={`rounded-lg p-3 text-sm font-sans ${
                answerData.isCorrect
                  ? "bg-brand-green-light text-brand-green border border-brand-mid"
                  : "bg-brand-amber-light text-brand-gold-dark border border-brand-gold-mid"
              }`}
            >
              {answerData.response}
            </div>
          )}

          <button
            type="button"
            onClick={handleReset}
            className="font-sans text-xs text-brand-primary hover:text-brand-dark underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          >
            Ask a different question
          </button>
        </div>
      )}
    </div>
  );
}
