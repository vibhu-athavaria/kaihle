import { useState } from "react";
import { X } from "lucide-react";
import { useConceptGuide } from "../../hooks/useConceptGuide";

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
  const { mutate, isPending, data, error, reset } = useConceptGuide();

  const handleGenerate = () => {
    reset();
    mutate({ subtopicId, question: question.trim() || undefined });
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

      {/* Optional question input */}
      {!data && (
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
              if (e.key === "Enter" && !isPending) handleGenerate();
            }}
          />
        </div>
      )}

      {/* Generate button */}
      {!data && (
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isPending}
          className="w-full bg-brand-primary text-white rounded-full py-2 px-4 text-sm font-sans font-medium disabled:opacity-60 disabled:cursor-not-allowed min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 transition-colors"
        >
          {isPending ? (
            <span className="flex items-center justify-center gap-2">
              <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
              <span className="animate-pulse">Generating explanation...</span>
            </span>
          ) : (
            "Explain this concept"
          )}
        </button>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-2 text-brand-red text-xs font-sans">
          Failed to generate explanation. Please try again.
          <button
            type="button"
            onClick={handleGenerate}
            className="ml-2 underline text-brand-primary"
          >
            Retry
          </button>
        </div>
      )}

      {/* Explanation result */}
      {data && (
        <div className="space-y-3">
          <p className="font-sans text-sm text-brand-ink leading-relaxed">
            {data.explanation}
          </p>
          <button
            type="button"
            onClick={() => {
              reset();
              setQuestion("");
            }}
            className="font-sans text-xs text-brand-primary hover:text-brand-dark underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          >
            Ask a different question
          </button>
        </div>
      )}
    </div>
  );
}
