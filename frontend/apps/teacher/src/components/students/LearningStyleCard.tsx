import { Video, Headphones, Book, Hand } from "lucide-react";

type Modality = "visual" | "auditory" | "reading_writing" | "kinesthetic";

const modalityIconMap: Record<Modality, React.ElementType> = {
  visual: Video,
  auditory: Headphones,
  reading_writing: Book,
  kinesthetic: Hand,
};

const modalityLabelMap: Record<Modality, string> = {
  visual: "Visual",
  auditory: "Auditory",
  reading_writing: "Reading & Writing",
  kinesthetic: "Hands-on",
};

interface LearningStyleCardProps {
  modalityScores: Record<string, number>;
  interests: string[];
}

function getDominantModality(
  modalityScores: Record<string, number> | undefined,
): Modality | null {
  if (!modalityScores || Object.keys(modalityScores).length === 0) return null;

  const entries = Object.entries(modalityScores) as [Modality, number][];
  const [dominant] = entries.reduce((max, current) =>
    current[1] > max[1] ? current : max,
  );

  return dominant;
}

export function LearningStyleCard({
  modalityScores,
  interests,
}: LearningStyleCardProps) {
  const dominantModality = getDominantModality(modalityScores);
  const IconComponent = dominantModality
    ? modalityIconMap[dominantModality]
    : null;

  return (
    <div className="bg-white rounded-2xl border border-brand-border shadow-sm p-5">
      <h2 className="font-display font-semibold text-lg text-brand-ink mb-4">
        Learning Style
      </h2>
      <div className="space-y-4">
        {dominantModality && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-brand-muted">Dominant modality:</span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-full text-sm font-medium">
              {IconComponent && (
                <IconComponent className="w-4 h-4" aria-hidden="true" />
              )}
              {modalityLabelMap[dominantModality]}
            </span>
          </div>
        )}

        {interests.length > 0 && (
          <div>
            <span className="text-sm text-brand-muted block mb-2">
              Top interests:
            </span>
            <div className="flex flex-wrap gap-2">
              {interests.map((interest: string) => (
                <span
                  key={interest}
                  className="px-2.5 py-1 bg-brand-green-light text-brand-primary text-xs font-medium rounded-full"
                >
                  {interest}
                </span>
              ))}
            </div>
          </div>
        )}

        {!dominantModality && interests.length === 0 && (
          <p className="text-sm text-brand-muted italic">
            No learning profile data available.
          </p>
        )}
      </div>
    </div>
  );
}
