import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface ModalityScore {
  modality: string;
  score: number;
}

interface LearningProfile {
  modalities: ModalityScore[];
  interests: string[];
  completed_at: string | null;
}

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
    const date = new Date(dateString);
    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  const getDominantModality = () => {
    if (!profile?.modalities || profile.modalities.length === 0) return null;
    return profile.modalities.reduce((prev, current) =>
      prev.score > current.score ? prev : current,
    );
  };

  const dominantModality = getDominantModality();

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
      <h2 className="font-fraunces text-base text-brand-ink px-6 pt-5 pb-3 border-b border-gray-50">
        Learning profile
      </h2>

      {isLoading ? (
        <div className="px-6 py-4 space-y-3">
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-gray-200 rounded w-3/4" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-2/3" />
            <div className="h-4 bg-gray-200 rounded w-1/3" />
          </div>
        </div>
      ) : (
        <>
          {/* Modality bars */}
          <div className="py-2 px-6">
            {profile?.modalities?.map((modality) => {
              const isDominant =
                dominantModality?.modality === modality.modality;
              return (
                <div
                  key={modality.modality}
                  className="flex items-center gap-3 py-2"
                >
                  <span className="text-sm text-gray-700 w-36 font-nunito">
                    {modality.modality}
                  </span>
                  <div className="h-2 rounded-full flex-1 bg-gray-100">
                    <div
                      className={`h-full rounded-full transition-all duration-600 ease-out ${
                        isDominant ? "bg-brand-primary" : "bg-gray-300"
                      }`}
                      style={{ width: `${modality.score * 100}%` }}
                      role="progressbar"
                      aria-valuenow={Math.round(modality.score * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${modality.modality} score`}
                    />
                  </div>
                  <span className="text-sm text-gray-500 w-10 text-right">
                    {Math.round(modality.score * 100)}%
                  </span>
                </div>
              );
            })}
          </div>

          {/* Interests */}
          {profile?.interests && profile.interests.length > 0 && (
            <div className="px-6 pb-4">
              <div className="flex flex-wrap gap-2">
                {profile.interests.map((interest) => (
                  <span
                    key={interest}
                    className="bg-green-50 text-brand-primary border border-green-200 text-xs rounded-full px-3 py-1"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Completed date */}
          {profile?.completed_at && (
            <div className="px-6 pb-4">
              <span className="text-xs text-gray-400">
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
            <p className="text-xs text-gray-400 mt-2 text-center">
              Retaking updates how your study plans and lesson activities are
              personalised for you. Takes about 5 minutes.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
