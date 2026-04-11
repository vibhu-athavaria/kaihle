import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { Modal } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { Video, Headphones, Book, Hand } from "lucide-react";

interface LearningProfileSidePanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  studentId: string | null;
  studentName: string | null;
  subtopicScores: Array<{
    subtopicName: string;
    topicName: string;
    masteryScore: number | null;
  }>;
}

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

function getDominantModality(
  modalityScores: Record<string, number> | undefined,
): Modality | null {
  if (!modalityScores) return null;

  const entries = Object.entries(modalityScores) as [Modality, number][];
  if (entries.length === 0) return null;

  const [dominant] = entries.reduce((max, current) =>
    current[1] > max[1] ? current : max,
  );

  return dominant;
}

export function LearningProfileSidePanel({
  open,
  onOpenChange,
  studentId,
  studentName,
  subtopicScores,
}: LearningProfileSidePanelProps) {
  const { data: profile, isLoading } = useQuery({
    queryKey: ["onboarding", "learning-profile", studentId],
    queryFn: async () => {
      const response = await apiClient.get(
        "/api/v1/onboarding/learning-profile",
        { params: { student_id: studentId } },
      );
      return response.data;
    },
    enabled: !!studentId && open,
  });

  const dominantModality = getDominantModality(profile?.modality_scores);
  const IconComponent = dominantModality
    ? modalityIconMap[dominantModality]
    : null;
  const topInterests = profile?.interests?.slice(0, 2) ?? [];

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={studentName ?? "Student Profile"}
      maxWidth="md"
    >
      <div className="space-y-6">
        {isLoading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-4 w-32 bg-gray-200 rounded" />
            <div className="h-4 w-48 bg-gray-100 rounded" />
          </div>
        ) : (
          <>
            {dominantModality && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-brand-muted">
                  Dominant modality:
                </span>
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-gold-light text-brand-gold-dark rounded-full text-sm font-medium">
                  {IconComponent && (
                    <IconComponent className="w-4 h-4" aria-hidden="true" />
                  )}
                  {modalityLabelMap[dominantModality]}
                </span>
              </div>
            )}

            {topInterests.length > 0 && (
              <div>
                <span className="text-sm text-brand-muted block mb-2">
                  Top interests:
                </span>
                <div className="flex flex-wrap gap-2">
                  {topInterests.map((interest: string) => (
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
          </>
        )}

        <div>
          <span className="text-sm text-brand-muted block mb-3">
            Subtopic mastery
          </span>
          <div className="space-y-2">
            {subtopicScores.map((score) => (
              <div
                key={score.subtopicName}
                className="flex items-center justify-between py-2 border-b border-brand-border last:border-0"
              >
                <div>
                  <div className="text-sm font-medium text-brand-ink">
                    {score.subtopicName}
                  </div>
                  <div className="text-xs text-brand-muted">
                    {score.topicName}
                  </div>
                </div>
                <div
                  className={`text-sm font-semibold ${
                    getMasteryStyle(score.masteryScore).textClass
                  }`}
                >
                  {score.masteryScore !== null
                    ? `${Math.round(score.masteryScore * 100)}%`
                    : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
