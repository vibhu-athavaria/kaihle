/**
 * QuestionBreakdown — per-question display for student attempt detail.
 *
 * Correct: shows "Answer: {text} ✓" in green.
 * Wrong: shows "Given: {text} ✕" in red AND "Correct: {text} ✓" in green.
 * Pagination: first 6 visible, "+ N more" button to expand, "Show less" to collapse.
 * Empty: "No answers submitted yet." in gray card.
 */
import { useState } from "react";
import type { QuestionAttempt } from "../../hooks/useAssessmentResults";

const PAGE_SIZE = 6;

interface QuestionBreakdownProps {
  questions: QuestionAttempt[];
}

interface QuestionRowProps {
  question: QuestionAttempt;
  index: number;
}

function QuestionRow({ question, index }: QuestionRowProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4">
      <div className="flex items-start gap-3 mb-3">
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-bold flex items-center justify-center">
          {index + 1}
        </span>
        <p className="text-sm text-brand-ink font-medium leading-relaxed">
          {question.questionText}
        </p>
      </div>

      <div className="ml-9 space-y-2">
        {question.isCorrect ? (
          /* Correct — single row only */
          <div className="bg-brand-green-light text-brand-green rounded-lg px-3 py-2 text-sm flex items-center gap-2">
            <span className="font-bold">Answer:</span>
            <span>{question.selectedAnswer ?? question.correctAnswer}</span>
            <span className="ml-auto font-bold" aria-label="Correct">
              ✓
            </span>
          </div>
        ) : (
          /* Wrong — two rows: given answer and correct answer */
          <>
            <div className="bg-brand-red-light text-brand-red rounded-lg px-3 py-2 text-sm flex items-center gap-2">
              <span className="font-bold">Given:</span>
              <span>{question.selectedAnswer ?? "—"}</span>
              <span className="ml-auto font-bold" aria-label="Incorrect">
                ✕
              </span>
            </div>
            <div className="bg-brand-green-light text-brand-green rounded-lg px-3 py-2 text-sm flex items-center gap-2">
              <span className="font-bold">Correct:</span>
              <span>{question.correctAnswer}</span>
              <span className="ml-auto font-bold" aria-label="Correct">
                ✓
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function QuestionBreakdown({ questions }: QuestionBreakdownProps) {
  const [expanded, setExpanded] = useState(false);

  if (questions.length === 0) {
    return (
      <div className="bg-gray-50 rounded-xl p-8 text-center">
        <p className="text-sm text-brand-muted">No answers submitted yet.</p>
      </div>
    );
  }

  const visible = expanded ? questions : questions.slice(0, PAGE_SIZE);
  const hiddenCount = questions.length - PAGE_SIZE;

  return (
    <div className="space-y-3">
      {visible.map((q, i) => (
        <QuestionRow key={q.questionId} question={q} index={i} />
      ))}

      {questions.length > PAGE_SIZE && (
        <div className="text-center pt-2">
          {expanded ? (
            <button
              onClick={() => setExpanded(false)}
              className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded px-3 py-1"
            >
              Show less
            </button>
          ) : (
            <button
              onClick={() => setExpanded(true)}
              className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded px-3 py-1"
            >
              + {hiddenCount} more question{hiddenCount !== 1 ? "s" : ""}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
