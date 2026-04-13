import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@kaihle/auth";
import { Button, Badge } from "@kaihle/ui";
import { toast } from "@kaihle/ui";
import { Calendar, BookOpen, CheckSquare } from "lucide-react";
import { useAssessmentWizard } from "../../../hooks/useAssessmentWizard";

function formatAssessmentType(type: string | null): string {
  if (!type) return "—";
  return type
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Step5Publish() {
  const navigate = useNavigate();
  const {
    classId,
    className,
    assessmentType,
    topicIds,
    previewQuestions,
    deadline,
    draftAssessmentId,
    reset,
    setStep,
  } = useAssessmentWizard();

  const [isPublishing, setIsPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  function handleSaveDraft() {
    const targetClassId = classId; // capture before reset clears store
    reset();
    navigate(`/teacher/classes/${targetClassId}/assessments`);
    toast.success("Assessment saved as draft.");
  }

  async function handlePublish() {
    if (!draftAssessmentId) return;
    setIsPublishing(true);
    setPublishError(null);

    const targetClassId = classId; // capture before reset clears store
    const targetAssessmentId = draftAssessmentId; // capture before reset clears store

    try {
      await apiClient.post(`/api/v1/assessments/${targetAssessmentId}/publish`);
      reset();
      navigate(`/teacher/classes/${targetClassId}/assessments?published=true`);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string } };
      };
      setPublishError(
        axiosErr?.response?.data?.detail ??
          "Failed to publish assessment. Please try again.",
      );
    } finally {
      setIsPublishing(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Summary card */}
      <div className="bg-white border border-brand-border rounded-xl p-5 space-y-4">
        <h3 className="font-display font-semibold text-lg text-brand-ink">
          Assessment Summary
        </h3>

        <div className="divide-y divide-brand-border-soft">
          <div className="flex items-center justify-between py-3">
            <span className="text-sm font-sans font-semibold text-brand-body">
              Class
            </span>
            <span className="text-sm font-sans text-brand-ink font-medium">
              {className ?? "—"}
            </span>
          </div>

          <div className="flex items-center justify-between py-3">
            <span className="text-sm font-sans font-semibold text-brand-body">
              Type
            </span>
            <Badge variant="info">{formatAssessmentType(assessmentType)}</Badge>
          </div>

          {topicIds.length > 0 && (
            <div className="flex items-start justify-between py-3 gap-4">
              <span className="text-sm font-sans font-semibold text-brand-body flex items-center gap-1.5">
                <BookOpen className="w-4 h-4" aria-hidden="true" />
                Topics
              </span>
              <span className="text-sm font-sans text-brand-ink text-right">
                {topicIds.length} topic{topicIds.length !== 1 ? "s" : ""}{" "}
                selected
              </span>
            </div>
          )}

          <div className="flex items-center justify-between py-3">
            <span className="text-sm font-sans font-semibold text-brand-body flex items-center gap-1.5">
              <CheckSquare className="w-4 h-4" aria-hidden="true" />
              Questions
            </span>
            <span className="text-sm font-sans text-brand-ink font-medium">
              {previewQuestions.length}
            </span>
          </div>

          <div className="flex items-center justify-between py-3">
            <span className="text-sm font-sans font-semibold text-brand-body flex items-center gap-1.5">
              <Calendar className="w-4 h-4" aria-hidden="true" />
              Deadline
            </span>
            <span className="text-sm font-sans text-brand-ink">
              {deadline
                ? new Date(deadline).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })
                : "No deadline"}
            </span>
          </div>
        </div>
      </div>

      {publishError && (
        <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
          <p className="text-sm font-sans text-brand-red">{publishError}</p>
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center pt-2">
        <Button variant="secondary" onClick={() => setStep(4)}>
          Back
        </Button>

        <div className="flex gap-3">
          <Button variant="secondary" onClick={handleSaveDraft}>
            Save as Draft
          </Button>
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
            loading={isPublishing}
            onClick={() => void handlePublish()}
          >
            Publish Now
          </Button>
        </div>
      </div>
    </div>
  );
}
