import { useState } from "react";
import { Modal, Button } from "@kaihle/ui";
import { useAddQuestion } from "../../hooks/useAssessmentQuestions";

interface Subtopic {
  id: string;
  name: string;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessmentId: string;
  subtopics: Subtopic[];
  onSuccess?: () => void;
}

const DEFAULT_OPTIONS = () => [
  { key: "A", text: "" },
  { key: "B", text: "" },
  { key: "C", text: "" },
  { key: "D", text: "" },
];

export function AddQuestionModal({
  open,
  onOpenChange,
  assessmentId,
  subtopics,
  onSuccess,
}: Props) {
  const [subtopicId, setSubtopicId] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] = useState("MCQ");
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [correctAnswer, setCorrectAnswer] = useState("");
  const [difficultyLevel, setDifficultyLevel] = useState(3);
  const [explanation, setExplanation] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const addMutation = useAddQuestion(assessmentId);

  function resetForm() {
    setSubtopicId("");
    setQuestionText("");
    setQuestionType("MCQ");
    setOptions(DEFAULT_OPTIONS());
    setCorrectAnswer("");
    setDifficultyLevel(3);
    setExplanation("");
    setErrorMsg(null);
  }

  async function handleSubmit() {
    setErrorMsg(null);
    if (!subtopicId) return setErrorMsg("Please select a subtopic.");
    if (!questionText.trim()) return setErrorMsg("Question text is required.");
    if (!correctAnswer) return setErrorMsg("Please select the correct answer.");
    if (questionType === "MCQ") {
      const filled = options.filter((o) => o.text.trim());
      if (filled.length < 2) return setErrorMsg("Add at least 2 options.");
    }

    try {
      await addMutation.mutateAsync({
        subtopic_id: subtopicId,
        question_text: questionText.trim(),
        question_type: questionType,
        options:
          questionType === "MCQ"
            ? options.filter((o) => o.key && o.text.trim())
            : null,
        correct_answer: correctAnswer,
        difficulty_level: difficultyLevel,
        explanation: explanation.trim() || null,
      });
      resetForm();
      onSuccess?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to add question.";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }

  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Add Question to Pool">
      <div className="space-y-4">
        <div className="bg-[#fffbeb] border border-[#fde68a] rounded-xl p-3">
          <p className="text-xs font-sans text-brand-gold-dark leading-relaxed">
            This question will be added immediately and submitted to KaihleAdmin
            for review. Once approved it becomes available to all schools.
          </p>
        </div>

        {/* Subtopic */}
        <div>
          <label
            htmlFor="add-q-subtopic"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Subtopic <span className="text-brand-red">*</span>
          </label>
          <select
            id="add-q-subtopic"
            value={subtopicId}
            onChange={(e) => setSubtopicId(e.target.value)}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          >
            <option value="">Select subtopic…</option>
            {subtopics.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Question type */}
        <div>
          <label className="block text-xs font-sans font-semibold text-brand-ink mb-1.5">
            Question Type
          </label>
          <div className="flex gap-2">
            {["MCQ", "TRUE_FALSE"].map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => {
                  setQuestionType(type);
                  setCorrectAnswer("");
                }}
                className={[
                  "px-3 py-1.5 rounded-lg text-xs font-sans font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold",
                  questionType === type
                    ? "bg-brand-gold-light border-brand-gold-mid text-brand-gold-dark"
                    : "bg-white border-brand-border text-brand-body hover:border-brand-gold-mid",
                ].join(" ")}
              >
                {type === "MCQ" ? "Multiple Choice" : "True / False"}
              </button>
            ))}
          </div>
        </div>

        {/* Question text */}
        <div>
          <label
            htmlFor="add-q-text"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Question Text <span className="text-brand-red">*</span>
          </label>
          <textarea
            id="add-q-text"
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            rows={3}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          />
        </div>

        {/* Options (MCQ only) */}
        {questionType === "MCQ" && (
          <div>
            <p className="text-xs font-sans font-semibold text-brand-ink mb-2">
              Options <span className="text-brand-red">*</span>
            </p>
            <div className="space-y-2">
              {options.map((opt, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="correct-answer"
                    value={opt.key}
                    checked={correctAnswer === opt.key}
                    onChange={() => setCorrectAnswer(opt.key)}
                    className="accent-brand-primary w-4 h-4 flex-shrink-0"
                    aria-label={`Mark option ${opt.key || i + 1} as correct`}
                  />
                  <span className="w-5 text-xs font-bold font-sans text-brand-muted flex-shrink-0">
                    {opt.key || String.fromCharCode(65 + i)}
                  </span>
                  <input
                    type="text"
                    value={opt.text}
                    onChange={(e) =>
                      setOptions((prev) =>
                        prev.map((o, j) =>
                          j === i ? { ...o, text: e.target.value } : o,
                        ),
                      )
                    }
                    placeholder={`Option ${opt.key || String.fromCharCode(65 + i)}`}
                    className="flex-1 border border-brand-border rounded-lg px-3 py-1.5 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                  />
                </div>
              ))}
            </div>
            <p className="mt-1.5 text-[10px] font-sans text-brand-muted">
              Select the radio button next to the correct answer.
            </p>
          </div>
        )}

        {/* True/False correct answer */}
        {questionType === "TRUE_FALSE" && (
          <div>
            <p className="text-xs font-sans font-semibold text-brand-ink mb-2">
              Correct Answer <span className="text-brand-red">*</span>
            </p>
            <div className="flex gap-3">
              {["true", "false"].map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setCorrectAnswer(val)}
                  className={[
                    "flex-1 py-2 rounded-xl border-[1.5px] text-sm font-sans font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
                    correctAnswer === val
                      ? "border-brand-primary bg-brand-light text-brand-primary"
                      : "border-brand-border text-brand-body hover:border-brand-border",
                  ].join(" ")}
                >
                  {val.charAt(0).toUpperCase() + val.slice(1)}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Difficulty */}
        <div>
          <label
            htmlFor="add-q-difficulty"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Difficulty Level:{" "}
            <span className="text-brand-gold-dark">
              {"⭐".repeat(difficultyLevel)}
            </span>
          </label>
          <input
            id="add-q-difficulty"
            type="range"
            min={1}
            max={5}
            value={difficultyLevel}
            onChange={(e) => setDifficultyLevel(parseInt(e.target.value, 10))}
            className="w-full accent-brand-gold"
          />
          <div className="flex justify-between text-[10px] font-sans text-brand-muted mt-0.5">
            <span>Easy (1)</span>
            <span>Hard (5)</span>
          </div>
        </div>

        {/* Explanation */}
        <div>
          <label
            htmlFor="add-q-explanation"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Explanation{" "}
            <span className="font-normal text-brand-muted">(optional)</span>
          </label>
          <textarea
            id="add-q-explanation"
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            rows={2}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
            placeholder="Shown to students after submission…"
          />
        </div>

        {errorMsg && (
          <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-3">
            <p className="text-xs font-sans text-brand-red">{errorMsg}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button
            variant="secondary"
            onClick={() => {
              resetForm();
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
            onClick={() => void handleSubmit()}
            disabled={addMutation.isPending}
          >
            {addMutation.isPending ? "Adding…" : "Add to Pool"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
