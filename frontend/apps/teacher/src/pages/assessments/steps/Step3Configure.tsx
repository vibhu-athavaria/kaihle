import { Button } from "@kaihle/ui";
import { useAssessmentWizard } from "../../../hooks/useAssessmentWizard";

export function Step3Configure() {
  const {
    assessmentType,
    questionsPerTopic,
    difficultyMin,
    difficultyMax,
    deadline,
    setQuestionsPerTopic,
    setDifficulty,
    setDeadline,
    setStep,
  } = useAssessmentWizard();

  const skipsTopics =
    assessmentType === "DIAGNOSTIC" || assessmentType === "FINAL";

  function handleDifficultyMinChange(value: number) {
    const clamped = Math.min(value, difficultyMax);
    setDifficulty(clamped, difficultyMax);
  }

  function handleDifficultyMaxChange(value: number) {
    const clamped = Math.max(value, difficultyMin);
    setDifficulty(difficultyMin, clamped);
  }

  return (
    <div className="space-y-8">
      {/* Question count */}
      <div>
        <label
          htmlFor="question-count"
          className="block text-sm font-sans font-semibold text-brand-ink mb-1"
        >
          Questions per Topic
        </label>
        <p className="text-xs font-sans text-brand-muted mb-3">
          Sampled from each topic you selected (1–20). Three or more per topic
          gives a more reliable read on each one.
        </p>
        <div className="flex items-center gap-4">
          <input
            id="question-count"
            type="range"
            min={1}
            max={20}
            step={1}
            value={questionsPerTopic}
            onChange={(e) => setQuestionsPerTopic(Number(e.target.value))}
            className="flex-1 h-2 rounded-full accent-brand-gold cursor-pointer"
            aria-valuemin={1}
            aria-valuemax={20}
            aria-valuenow={questionsPerTopic}
          />
          <span className="w-24 text-center text-sm font-sans font-bold text-brand-ink bg-brand-gold-light border border-brand-gold-mid rounded-lg px-3 py-1.5">
            {questionsPerTopic} per topic
          </span>
        </div>
      </div>

      {/* Difficulty range */}
      <div>
        <p className="text-sm font-sans font-semibold text-brand-ink mb-1">
          Difficulty Range
        </p>
        <p className="text-xs font-sans text-brand-muted mb-3">
          Questions with difficulty between these values will be included
          (1.0–5.0)
        </p>
        <div className="grid grid-cols-2 gap-4 max-w-xs">
          <div>
            <label
              htmlFor="difficulty-min"
              className="block text-xs font-sans font-semibold text-brand-body mb-1"
            >
              Minimum
            </label>
            <input
              id="difficulty-min"
              type="number"
              min={1.0}
              max={5.0}
              step={0.5}
              value={difficultyMin}
              onChange={(e) =>
                handleDifficultyMinChange(Number(e.target.value))
              }
              className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
            />
          </div>
          <div>
            <label
              htmlFor="difficulty-max"
              className="block text-xs font-sans font-semibold text-brand-body mb-1"
            >
              Maximum
            </label>
            <input
              id="difficulty-max"
              type="number"
              min={1.0}
              max={5.0}
              step={0.5}
              value={difficultyMax}
              onChange={(e) =>
                handleDifficultyMaxChange(Number(e.target.value))
              }
              className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
            />
          </div>
        </div>
        {difficultyMin > difficultyMax && (
          <p className="mt-1 text-xs font-sans text-brand-red">
            Minimum difficulty cannot exceed maximum.
          </p>
        )}
      </div>

      {/* Deadline */}
      <div>
        <label
          htmlFor="deadline"
          className="block text-sm font-sans font-semibold text-brand-ink mb-1"
        >
          Deadline{" "}
          <span className="font-normal text-brand-muted">(optional)</span>
        </label>
        <input
          id="deadline"
          type="date"
          value={deadline ?? ""}
          onChange={(e) => setDeadline(e.target.value || null)}
          min={new Date().toISOString().split("T")[0]}
          className="border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
        />
        {deadline && (
          <button
            type="button"
            onClick={() => setDeadline(null)}
            className="ml-3 text-xs font-sans text-brand-muted hover:text-brand-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
          >
            Clear
          </button>
        )}
      </div>

      {/* Footer */}
      <div className="flex justify-between pt-2">
        <Button
          variant="secondary"
          onClick={() => setStep(skipsTopics ? 1 : 2)}
        >
          Back
        </Button>
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          onClick={() => setStep(4)}
        >
          Preview Questions
        </Button>
      </div>
    </div>
  );
}
