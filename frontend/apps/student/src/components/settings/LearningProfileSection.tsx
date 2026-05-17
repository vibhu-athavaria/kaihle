import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface WorkStyle {
  prefers_solo?: boolean;
  short_sessions?: boolean;
  task_based?: boolean;
  [key: string]: boolean | undefined;
}

interface LearningProfile {
  modality_scores: Record<string, number>;
  work_style: WorkStyle | null;
  interests: string[] | null;
  completed_at: string | null;
}

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

export function LearningProfileSection() {
  const navigate = useNavigate();

  const { data: profile, isLoading } = useQuery<LearningProfile>({
    queryKey: ["student", "settings", "learning-profile"],
    queryFn: async () => {
      const response = await apiClient.get<LearningProfile>(
        "/api/v1/onboarding/learning-profile",
      );
      return response.data;
    },
  });

  const handleRetake = () => {
    navigate("/student/onboarding/profile");
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "—";
    return new Date(dateString).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  // Filter to numeric-score entries only (old v2 profiles stored {dominant, secondary} strings)
  const modalityEntries = profile?.modality_scores
    ? Object.entries(profile.modality_scores)
        .filter(([, v]) => typeof v === "number")
        .sort((a, b) => (b[1] as number) - (a[1] as number))
    : [];

  const dominantModality =
    modalityEntries.length > 0 ? modalityEntries[0][0] : null;

  const workStyle = profile?.work_style ?? null;

  return (
    <div className="bg-white rounded-2xl border border-brand-border shadow-sm">
      <h2 className="font-display text-base text-brand-ink px-6 pt-5 pb-3 border-b border-brand-border-soft">
        Learning profile
      </h2>

      {isLoading ? (
        <div className="px-6 py-4 space-y-3">
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-brand-border rounded w-3/4" />
            <div className="h-4 bg-brand-border rounded w-1/2" />
            <div className="h-4 bg-brand-border rounded w-2/3" />
            <div className="h-4 bg-brand-border rounded w-1/3" />
          </div>
        </div>
      ) : (
        <>
          {/* Modality bars */}
          <div className="py-2 px-6">
            {modalityEntries.map(([key, score]) => {
              const isDominant = dominantModality === key;
              return (
                <div key={key} className="flex items-center gap-3 py-2">
                  <span className="font-sans text-sm text-brand-ink w-36">
                    {MODALITY_LABELS[key] ?? key}
                  </span>
                  <div className="h-2 rounded-full flex-1 bg-brand-primary/10">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ease-out ${
                        isDominant ? "bg-brand-primary" : "bg-brand-primary/30"
                      }`}
                      style={{ width: `${score * 100}%` }}
                      role="progressbar"
                      aria-valuenow={Math.round(score * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${MODALITY_LABELS[key] ?? key} score`}
                    />
                  </div>
                  <span className="font-sans text-sm text-brand-body w-10 text-right">
                    {Math.round(score * 100)}%
                  </span>
                </div>
              );
            })}
          </div>

          {/* Work style chips */}
          {workStyle && (
            <div className="px-6 pb-4">
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

          {/* Profile impact explainer */}
          <div className="px-6 pb-4">
            <p className="font-sans text-xs text-brand-muted">
              Kaihle uses your learning profile to personalise how the AI
              Concept Guide explains topics to you.
            </p>
          </div>

          {/* Interests */}
          {profile?.interests && profile.interests.length > 0 && (
            <div className="px-6 pb-4">
              <div className="flex flex-wrap gap-2">
                {profile.interests.map((interest) => (
                  <span
                    key={interest}
                    className="bg-green-50 text-brand-primary border border-green-200 text-xs rounded-full px-3 py-1 font-medium"
                  >
                    {INTEREST_LABELS[interest] ?? interest}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Completed date */}
          {profile?.completed_at && (
            <div className="px-6 pb-4">
              <span className="font-sans text-xs text-brand-muted">
                Completed {formatDate(profile.completed_at)}
              </span>
            </div>
          )}

          {/* Retake button */}
          <div className="mx-6 mb-6">
            <button
              type="button"
              onClick={handleRetake}
              className="border border-brand-primary text-brand-primary rounded-xl px-4 py-2 text-sm font-medium w-full hover:bg-green-50 transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              Retake questionnaire
            </button>
            <p className="font-sans text-xs text-brand-muted mt-2 text-center">
              Retaking updates how your study plans and lesson activities are
              personalised for you. Takes about 5 minutes.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
