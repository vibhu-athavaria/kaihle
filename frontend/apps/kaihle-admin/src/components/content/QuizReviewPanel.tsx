import { useState } from "react";
import {
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
} from "lucide-react";
import type {
  QuizSection,
  QuizQuestionEntry,
} from "../../hooks/useSubtopicContent";

interface QuizReviewPanelProps {
  quiz: QuizSection;
  onSave: (
    questions: QuizQuestionEntry[],
    status: "approved" | "rejected",
  ) => void;
  isSaving?: boolean;
}

// ── Difficulty badge ────────────────────────────────────────────────────────

function DifficultyBadge({ level }: { level: number | null }) {
  if (level === null) return null;
  const colors = [
    "",
    "bg-green-50 text-green-700 border-green-200",
    "bg-green-50 text-green-700 border-green-200",
    "bg-amber-50 text-amber-700 border-amber-200",
    "bg-orange-50 text-orange-700 border-orange-200",
    "bg-red-50 text-red-700 border-red-200",
  ];
  const labels = ["", "Easy", "Easy", "Medium", "Hard", "Hard"];
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${colors[level] ?? "bg-gray-100 text-gray-600 border-gray-200"}`}
    >
      D{level} {labels[level]}
    </span>
  );
}

// ── Single question editor ──────────────────────────────────────────────────

interface QuestionEditorProps {
  question: QuizQuestionEntry;
  index: number;
  onUpdate: (q: QuizQuestionEntry) => void;
  onDelete: () => void;
}

function QuestionEditor({
  question,
  index,
  onUpdate,
  onDelete,
}: QuestionEditorProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Collapsed header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 text-gray-600 text-xs font-bold flex items-center justify-center">
          {index + 1}
        </span>
        <p className="flex-1 text-sm text-gray-800 truncate">
          {question.question_text || "Untitled question"}
        </p>
        <DifficultyBadge level={question.difficulty_level ?? null} />
        {open ? (
          <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
          {/* Question text */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Question
            </label>
            <textarea
              value={question.question_text}
              onChange={(e) =>
                onUpdate({ ...question, question_text: e.target.value })
              }
              rows={2}
              className="w-full border border-gray-300 rounded-md px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary resize-none"
            />
          </div>

          {/* Options */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Options
            </label>
            <div className="space-y-1.5">
              {question.options.map((opt, oi) => {
                const key = String.fromCharCode(65 + oi); // A B C D
                const isCorrect = question.correct_answer === key;
                return (
                  <div key={oi} className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        onUpdate({ ...question, correct_answer: key })
                      }
                      className={`flex-shrink-0 w-6 h-6 rounded-full border-2 text-[10px] font-bold transition-colors ${
                        isCorrect
                          ? "bg-brand-primary border-brand-primary text-white"
                          : "border-gray-300 text-gray-500 hover:border-brand-primary"
                      }`}
                    >
                      {key}
                    </button>
                    <input
                      type="text"
                      value={opt.replace(/^[A-D]:\s*/, "")}
                      onChange={(e) => {
                        const updated = [...question.options];
                        updated[oi] = `${key}: ${e.target.value}`;
                        onUpdate({ ...question, options: updated });
                      }}
                      className="flex-1 border border-gray-300 rounded-md px-2.5 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Explanation + difficulty row */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Explanation
              </label>
              <input
                type="text"
                value={question.explanation}
                onChange={(e) =>
                  onUpdate({ ...question, explanation: e.target.value })
                }
                className="w-full border border-gray-300 rounded-md px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
                placeholder="Why the correct answer is correct…"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Difficulty (1–5)
              </label>
              <input
                type="number"
                min={1}
                max={5}
                value={question.difficulty_level ?? ""}
                onChange={(e) =>
                  onUpdate({
                    ...question,
                    difficulty_level: e.target.value
                      ? parseInt(e.target.value, 10)
                      : null,
                  })
                }
                className="w-full border border-gray-300 rounded-md px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
              />
            </div>
          </div>

          {/* Delete */}
          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={onDelete}
              className="inline-flex items-center gap-1 text-xs text-red-500 hover:text-red-700 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Remove question
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main panel ──────────────────────────────────────────────────────────────

export function QuizReviewPanel({
  quiz,
  onSave,
  isSaving = false,
}: QuizReviewPanelProps) {
  const [questions, setQuestions] = useState<QuizQuestionEntry[]>([
    ...quiz.questions,
  ]);
  const isDirty = JSON.stringify(questions) !== JSON.stringify(quiz.questions);

  const isApproved = quiz.review_status === "approved";
  const isRejected = quiz.review_status === "rejected";

  const updateQuestion = (index: number, q: QuizQuestionEntry) => {
    const updated = [...questions];
    updated[index] = q;
    setQuestions(updated);
  };

  const deleteQuestion = (index: number) => {
    setQuestions((qs) => qs.filter((_, i) => i !== index));
  };

  const addQuestion = () => {
    const newId = `q${Date.now()}`;
    setQuestions((qs) => [
      ...qs,
      {
        question_id: newId,
        question_text: "",
        options: ["A: ", "B: ", "C: ", "D: "],
        correct_answer: "A",
        explanation: "",
        difficulty_level: 3,
      },
    ]);
  };

  const canSubmit =
    questions.length > 0 &&
    questions.every((q) => q.question_text.trim().length > 5);

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
            isApproved
              ? "bg-green-50 text-brand-primary border border-green-200"
              : isRejected
                ? "bg-red-50 text-red-700 border border-red-200"
                : "bg-amber-50 text-amber-700 border border-amber-200"
          }`}
        >
          {isApproved ? "Approved" : isRejected ? "Rejected" : "Pending review"}
        </span>
        <span className="text-xs text-role-admin-muted">
          {questions.length} questions
        </span>
        {isDirty && (
          <span className="text-xs text-amber-600 font-medium">
            ● Unsaved changes
          </span>
        )}
      </div>

      {/* Question list */}
      <div className="space-y-2">
        {questions.map((q, i) => (
          <QuestionEditor
            key={q.question_id}
            question={q}
            index={i}
            onUpdate={(updated) => updateQuestion(i, updated)}
            onDelete={() => deleteQuestion(i)}
          />
        ))}
      </div>

      {/* Add question */}
      <button
        type="button"
        onClick={addQuestion}
        className="w-full py-2.5 border-2 border-dashed border-gray-300 hover:border-brand-primary/50 rounded-lg text-xs text-gray-500 hover:text-brand-primary transition-colors flex items-center justify-center gap-1.5"
      >
        <Plus className="w-3.5 h-3.5" />
        Add question
      </button>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          disabled={isSaving || !canSubmit}
          onClick={() => onSave(questions, "rejected")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-red-200 text-red-600 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <XCircle className="w-3.5 h-3.5" />
          Reject
        </button>
        <button
          type="button"
          disabled={isSaving || !canSubmit}
          onClick={() => onSave(questions, "approved")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-primary text-white text-xs font-medium rounded-lg hover:bg-brand-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? (
            <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <CheckCircle className="w-3.5 h-3.5" />
          )}
          {isSaving ? "Saving…" : isDirty ? "Save & Approve" : "Approve"}
        </button>
      </div>
    </div>
  );
}
