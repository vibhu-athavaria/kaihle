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

function DifficultyDots({ level }: { level: number }) {
  return (
    <span
      className="inline-flex gap-0.5"
      aria-label={`Difficulty ${level} of 5`}
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i < level ? "bg-brand-muted" : "bg-brand-border"}`}
        />
      ))}
    </span>
  );
}

function QuestionRow({ question, index }: QuestionRowProps) {
  return (
    <div className="bg-white rounded-xl border border-brand-border p-4">
      {/* Subtopic chip + difficulty */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-brand-muted bg-brand-bg rounded-full px-2 py-0.5">
          {question.subtopic_name}
        </span>
        <DifficultyDots level={question.difficulty_level} />
      </div>

      <div className="flex items-start gap-3 mb-3">
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-border-soft text-brand-muted text-xs font-bold flex items-center justify-center">
          {index + 1}
        </span>
        <p className="text-sm text-brand-ink font-medium leading-relaxed">
          {question.question_text}
        </p>
      </div>

      <div className="ml-9 space-y-2">
        {question.is_correct ? (
          /* Correct — single row only */
          <div className="bg-green-50 text-green-700 rounded-lg px-3 py-2 text-sm flex items-center gap-2">
            <span className="font-bold">Answer:</span>
            <span>{question.selected_key ?? question.correct_answer}</span>
            <span className="ml-auto font-bold" aria-label="Correct">
              ✓
            </span>
          </div>
        ) : (
          /* Wrong — two rows: given answer and correct answer */
          <>
            <div className="bg-red-50 text-red-700 rounded-lg px-3 py-2 text-sm flex items-center gap-2">
              <span className="font-bold">Given:</span>
              <span>{question.selected_key ?? "—"}</span>
              <span className="ml-auto font-bold" aria-label="Incorrect">
                ✕
              </span>
            </div>
            <div className="bg-green-50 text-green-700 rounded-lg px-3 py-2 text-sm flex items-center gap-2">
              <span className="font-bold">Correct:</span>
              <span>{question.correct_answer}</span>
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
      <div className="bg-brand-bg rounded-xl p-8 text-center">
        <p className="text-sm text-brand-muted">No answers submitted yet.</p>
      </div>
    );
  }

  const visible = expanded ? questions : questions.slice(0, PAGE_SIZE);
  const hiddenCount = questions.length - PAGE_SIZE;

  return (
    <div className="space-y-3">
      {visible.map((q, i) => (
        <QuestionRow key={q.question_id} question={q} index={i} />
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
