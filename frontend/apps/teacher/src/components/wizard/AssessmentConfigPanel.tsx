interface AssessmentConfigPanelProps {
  questionsPerTopic: number;
  onQuestionsPerTopicChange: (n: number) => void;
  timeLimitMinutes: number | null;
  onTimeLimitChange: (n: number | null) => void;
  questionTypes: string[];
  onQuestionTypesChange: (types: string[]) => void;
  minimumDifficulty: number;
  maximumDifficulty: number;
  onDifficultyChange: (min: number, max: number) => void;
}

export function AssessmentConfigPanel({
  questionsPerTopic,
  onQuestionsPerTopicChange,
  timeLimitMinutes,
  onTimeLimitChange,
  questionTypes,
  onQuestionTypesChange,
  minimumDifficulty,
  maximumDifficulty,
  onDifficultyChange,
}: AssessmentConfigPanelProps) {
  function toggleQuestionType(type: string) {
    if (questionTypes.includes(type)) {
      onQuestionTypesChange(questionTypes.filter((t) => t !== type));
    } else {
      onQuestionTypesChange([...questionTypes, type]);
    }
  }

  return (
    <div className="border border-[#e5e7eb] rounded-[8px] overflow-hidden">
      {/* Panel header — intentionally small caps label */}
      <div className="px-3 py-2 bg-[#f9fafb] border-b border-[#e5e7eb] text-[10px] font-bold uppercase tracking-[0.7px] text-brand-muted">
        Assessment Settings
      </div>

      {/* Questions per topic */}
      <div className="px-3 py-3 border-b border-[#f3f4f6]">
        <div className="text-sm font-bold text-brand-ink mb-[6px]">
          Questions per topic
        </div>
        <input
          type="number"
          min={3}
          max={20}
          value={questionsPerTopic}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            if (!isNaN(v) && v >= 3 && v <= 20) onQuestionsPerTopicChange(v);
          }}
          className="w-16 border border-[#e5e7eb] rounded-[6px] px-[10px] py-[5px] text-sm font-sans text-brand-ink outline-none focus-visible:border-brand-gold focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-0"
          aria-label="Questions per topic"
        />
        <div className="text-xs text-brand-muted mt-1">
          Min 3 for reliable placement · each student sees exactly this many per
          topic
        </div>
      </div>

      {/* Time limit */}
      <div className="px-3 py-3 border-b border-[#f3f4f6]">
        <div className="text-sm font-bold text-brand-ink mb-[6px]">
          Time limit{" "}
          <span className="font-normal text-brand-muted">(optional)</span>
        </div>
        <div className="flex items-center gap-[6px]">
          <input
            type="number"
            min={1}
            max={300}
            placeholder="—"
            value={timeLimitMinutes ?? ""}
            onChange={(e) => {
              const raw = e.target.value;
              if (raw === "") {
                onTimeLimitChange(null);
              } else {
                const v = parseInt(raw, 10);
                if (!isNaN(v) && v >= 1 && v <= 300) onTimeLimitChange(v);
              }
            }}
            className="w-16 border border-[#e5e7eb] rounded-[6px] px-[10px] py-[5px] text-sm font-sans text-brand-ink outline-none focus-visible:border-brand-gold focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-0"
            aria-label="Time limit in minutes"
          />
          <span className="text-sm text-brand-muted">min</span>
        </div>
        <div className="text-xs text-brand-muted mt-1">
          Leave blank = untimed
        </div>
      </div>

      {/* Question types */}
      <div className="px-3 py-3 border-b border-[#f3f4f6]">
        <div className="text-sm font-bold text-brand-ink mb-[6px]">
          Question types
        </div>
        <div className="flex flex-col gap-[5px]">
          {[
            { value: "MCQ", label: "MCQ" },
            { value: "TRUE_FALSE", label: "True / False" },
          ].map(({ value, label }) => (
            <label
              key={value}
              className="flex items-center gap-[7px] text-sm text-brand-ink cursor-pointer min-h-[24px]"
            >
              <input
                type="checkbox"
                checked={questionTypes.includes(value)}
                onChange={() => toggleQuestionType(value)}
                className="w-4 h-4 accent-[#c9932a] focus-visible:ring-2 focus-visible:ring-brand-gold"
                aria-label={label}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Difficulty range */}
      <div className="px-3 py-3">
        <div className="text-sm font-bold text-brand-ink mb-[6px]">
          Difficulty range
        </div>
        <div className="flex gap-2 items-center mb-2">
          <div>
            <div className="text-xs text-brand-muted mb-[3px]">Min</div>
            <input
              type="number"
              min={1}
              max={5}
              value={minimumDifficulty}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!isNaN(v) && v >= 1 && v <= 5)
                  onDifficultyChange(v, Math.max(v, maximumDifficulty));
              }}
              className="w-[52px] border border-[#e5e7eb] rounded-[6px] px-[10px] py-[5px] text-sm font-sans text-brand-ink outline-none focus-visible:border-brand-gold focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-0"
              aria-label="Minimum difficulty"
            />
          </div>
          <div className="text-sm text-brand-muted mt-4">–</div>
          <div>
            <div className="text-xs text-brand-muted mb-[3px]">Max</div>
            <input
              type="number"
              min={1}
              max={5}
              value={maximumDifficulty}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!isNaN(v) && v >= 1 && v <= 5)
                  onDifficultyChange(Math.min(v, minimumDifficulty), v);
              }}
              className="w-[52px] border border-[#e5e7eb] rounded-[6px] px-[10px] py-[5px] text-sm font-sans text-brand-ink outline-none focus-visible:border-brand-gold focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-0"
              aria-label="Maximum difficulty"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
