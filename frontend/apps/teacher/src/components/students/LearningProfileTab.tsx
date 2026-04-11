const modalityLabels: Record<string, string> = {
  visual: "Visual",
  auditory: "Auditory",
  reading_writing: "Reading/Writing",
  kinesthetic: "Hands-on",
};

interface LearningProfileTabProps {
  modalityScores: Record<string, number>;
  workStyle?: {
    prefers_solo?: boolean;
    short_sessions?: boolean;
    task_based?: boolean;
  };
  interests: string[];
}

export function LearningProfileTab({
  modalityScores,
  interests,
}: LearningProfileTabProps) {
  const dominantModality = Object.entries(modalityScores).reduce(
    (max, curr) => (curr[1] > max[1] ? curr : max),
    ["", 0] as [string, number],
  )[0];

  const modalityEntries = Object.entries(modalityScores).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-display font-semibold text-sm text-brand-ink mb-3">
          Learning Style
        </h3>
        <div className="space-y-2">
          {modalityEntries.map(([key, value]) => (
            <div key={key} className="flex items-center gap-3 py-1">
              <span className="font-sans text-sm text-brand-body w-32 flex-shrink-0">
                {modalityLabels[key] ?? key}
              </span>
              <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    key === dominantModality ? "bg-brand-gold" : "bg-gray-200"
                  }`}
                  style={{ width: `${Math.round(value * 100)}%` }}
                />
              </div>
              <span className="font-sans text-sm text-brand-muted w-10 text-right">
                {Math.round(value * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {interests.length > 0 && (
        <div>
          <h3 className="font-display font-semibold text-sm text-brand-ink mb-3">
            Interests
          </h3>
          <div className="flex flex-wrap gap-2">
            {interests.map((interest) => (
              <span
                key={interest}
                className="bg-gray-100 text-brand-body rounded-full px-3 py-1 text-xs font-sans"
              >
                {interest}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
