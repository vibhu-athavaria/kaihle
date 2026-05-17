const MODALITY_LABELS: Record<string, string> = {
  visual: "Visual",
  auditory: "Auditory",
  reading_writing: "Reading / Writing",
  kinesthetic: "Hands-on",
};

const INTEREST_LABELS: Record<string, string> = {
  sports_movement: "Sports & Movement",
  tech_gaming: "Tech & Gaming",
  nature_animals: "Nature & Animals",
  arts_culture: "Arts & Culture",
};

const MODALITY_EMOJI: Record<string, string> = {
  visual: "👁️",
  auditory: "👂",
  reading_writing: "📖",
  kinesthetic: "🤲",
};

const TEACHING_TIPS: Record<string, string> = {
  visual: "Use diagrams, colour coding, and visual organisers",
  auditory: "Include verbal explanations and think-aloud moments",
  reading_writing: "Provide written notes and encourage written responses",
  kinesthetic: "Use hands-on activities and physical models",
};

interface WorkStyle {
  prefers_solo?: boolean;
  short_sessions?: boolean;
  task_based?: boolean;
  [key: string]: boolean | undefined;
}

interface LearningProfileTabProps {
  modalityScores: Record<string, number>;
  workStyle?: WorkStyle | null;
  interests: string[];
  completedAt?: string | null;
}

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function LearningProfileTab({
  modalityScores,
  workStyle,
  interests,
  completedAt,
}: LearningProfileTabProps) {
  // Always render the 4 known modality keys in order — coerce missing/invalid values to 0.
  // This naturally excludes old-format keys (dominant, secondary) from broken v2 profiles.
  const MODALITY_KEYS = [
    "visual",
    "auditory",
    "reading_writing",
    "kinesthetic",
  ] as const;
  const modalityEntries = MODALITY_KEYS.map((key): [string, number] => [
    key,
    typeof modalityScores[key] === "number"
      ? (modalityScores[key] as number)
      : 0,
  ]).sort((a, b) => b[1] - a[1]);

  const dominantModality =
    modalityEntries.length > 0 ? modalityEntries[0][0] : "";

  // Top 2 tips by modality score + optional short_sessions tip
  const topTips = modalityEntries
    .slice(0, 2)
    .map(([key]) => TEACHING_TIPS[key])
    .filter(Boolean);
  if (workStyle?.short_sessions === true) {
    topTips.push("Break tasks into short focused chunks");
  }

  return (
    <div className="space-y-6">
      {/* Section 1 — Dominant modality headline */}
      {dominantModality && (
        <div className="flex items-center gap-3 p-4 bg-brand-gold/10 rounded-xl border border-brand-gold/20">
          <span className="text-2xl" aria-hidden="true">
            {MODALITY_EMOJI[dominantModality] ?? "🧠"}
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-brand-muted">
              Dominant learning style
            </p>
            <p className="font-display font-bold text-lg text-brand-ink">
              {MODALITY_LABELS[dominantModality] ?? dominantModality}
            </p>
          </div>
        </div>
      )}

      {/* Section 2 — All modality bars */}
      <div>
        <h3 className="font-display font-semibold text-sm text-brand-ink mb-3">
          Learning style breakdown
        </h3>
        <div className="space-y-2">
          {modalityEntries.map(([key, rawValue]) => {
            const value = Number(rawValue) || 0;
            const pct = Math.round(value * 100);
            return (
              <div key={key} className="flex items-center gap-3 py-1">
                <span className="font-sans text-sm text-brand-body w-36 flex-shrink-0">
                  {MODALITY_LABELS[key] ?? key}
                </span>
                <div className="flex-1 h-2.5 bg-brand-gold/10 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      key === dominantModality
                        ? "bg-brand-gold"
                        : "bg-brand-gold/30"
                    }`}
                    style={{ width: `${pct}%` }}
                    role="progressbar"
                    aria-valuenow={pct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${MODALITY_LABELS[key] ?? key} score`}
                  />
                </div>
                <span className="font-sans text-sm text-brand-muted w-10 text-right">
                  {pct}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3 — Work style chips */}
      {workStyle && (
        <div>
          <h3 className="font-display font-semibold text-sm text-brand-ink mb-3">
            Work style
          </h3>
          <div className="flex flex-wrap gap-2">
            {workStyle.prefers_solo === true && (
              <span className="px-3 py-1 bg-gray-100 text-brand-ink text-xs font-sans font-medium rounded-full">
                Prefers solo work
              </span>
            )}
            {workStyle.prefers_solo === false && (
              <span className="px-3 py-1 bg-gray-100 text-brand-ink text-xs font-sans font-medium rounded-full">
                Prefers group work
              </span>
            )}
            {workStyle.short_sessions === true && (
              <span className="px-3 py-1 bg-gray-100 text-brand-ink text-xs font-sans font-medium rounded-full">
                Short sessions
              </span>
            )}
            {workStyle.short_sessions === false && (
              <span className="px-3 py-1 bg-gray-100 text-brand-ink text-xs font-sans font-medium rounded-full">
                Long sessions
              </span>
            )}
            {workStyle.task_based === true && (
              <span className="px-3 py-1 bg-gray-100 text-brand-ink text-xs font-sans font-medium rounded-full">
                Task-based
              </span>
            )}
            {workStyle.task_based === false && (
              <span className="px-3 py-1 bg-gray-100 text-brand-ink text-xs font-sans font-medium rounded-full">
                Exploration-based
              </span>
            )}
          </div>
        </div>
      )}

      {/* Section 4 — Interests */}
      {interests.length > 0 && (
        <div>
          <h3 className="font-display font-semibold text-sm text-brand-ink mb-3">
            Interests
          </h3>
          <div className="flex flex-wrap gap-2">
            {interests.map((interest) => (
              <span
                key={interest}
                className="bg-brand-gold/10 text-brand-gold-dark border border-brand-gold/20 rounded-full px-3 py-1 text-xs font-sans font-medium"
              >
                {INTEREST_LABELS[interest] ?? interest}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Section 5 — Teaching implications */}
      {topTips.length > 0 && (
        <div>
          <h3 className="font-display font-semibold text-sm text-brand-ink mb-3">
            Teaching implications
          </h3>
          <div className="space-y-1.5">
            {topTips.map((tip) => (
              <div
                key={tip}
                className="flex items-start gap-2 text-sm text-brand-body"
              >
                <span className="text-brand-gold mt-0.5" aria-hidden="true">
                  •
                </span>
                {tip}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Section 6 — Profile completion date */}
      {completedAt && (
        <p className="font-sans text-xs text-brand-muted">
          Profile completed {formatDate(completedAt)}
        </p>
      )}
    </div>
  );
}
