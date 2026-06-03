import { useState, useEffect } from "react";
import { Modal, Button } from "@kaihle/ui";
import { AlertTriangle } from "lucide-react";
import {
  useUpdateAssessment,
  type AssessmentPreview,
  type AssessmentUpdatePayload,
} from "../../hooks/useAssessmentPreview";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessment: AssessmentPreview;
  classId: string;
  onSuccess?: () => void;
}

export function EditAssessmentDetailsModal({
  open,
  onOpenChange,
  assessment,
  classId,
  onSuccess,
}: Props) {
  const [title, setTitle] = useState(assessment.title);
  const [instructions, setInstructions] = useState(
    assessment.instructions ?? "",
  );
  const [deadline, setDeadline] = useState(
    assessment.deadline
      ? new Date(assessment.deadline).toISOString().slice(0, 16)
      : "",
  );
  const [questionCount, setQuestionCount] = useState(
    assessment.question_count ?? "",
  );
  const [timeLimitMinutes, setTimeLimitMinutes] = useState(
    assessment.time_limit_minutes,
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [dirtyRiskyFields, setDirtyRiskyFields] = useState<Set<string>>(
    new Set(),
  );

  const isClosed = assessment.status === "CLOSED";
  const hasAttempts = assessment.attempt_count > 0;
  const showRiskyWarning =
    hasAttempts && dirtyRiskyFields.size > 0 && !isClosed;

  const updateMutation = useUpdateAssessment(assessment.id, classId);

  // Reset form state when modal opens
  useEffect(() => {
    if (open) {
      setTitle(assessment.title);
      setInstructions(assessment.instructions ?? "");
      setDeadline(
        assessment.deadline
          ? new Date(assessment.deadline).toISOString().slice(0, 16)
          : "",
      );
      setQuestionCount(assessment.question_count ?? "");
      setTimeLimitMinutes(assessment.time_limit_minutes);
      setErrorMsg(null);
      setDirtyRiskyFields(new Set());
    }
  }, [open, assessment]);

  function markRisky(field: string) {
    setDirtyRiskyFields((prev) => new Set([...prev, field]));
  }

  async function handleSave() {
    setErrorMsg(null);
    const payload: AssessmentUpdatePayload = {};

    if (title !== assessment.title) payload.title = title;
    if (instructions !== (assessment.instructions ?? ""))
      payload.instructions = instructions || null;
    if (
      deadline !==
      (assessment.deadline
        ? new Date(assessment.deadline).toISOString().slice(0, 16)
        : "")
    )
      payload.deadline = deadline ? new Date(deadline).toISOString() : null;

    if (!isClosed) {
      const qc =
        typeof questionCount === "string"
          ? parseInt(questionCount, 10)
          : questionCount;
      if (!isNaN(qc) && qc !== assessment.question_count)
        payload.question_count = qc;
      if (timeLimitMinutes !== assessment.time_limit_minutes)
        payload.time_limit_minutes = timeLimitMinutes;
    }

    if (Object.keys(payload).length === 0) {
      onOpenChange(false);
      return;
    }

    try {
      await updateMutation.mutateAsync(payload);
      onSuccess?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to update assessment. Please try again.";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Edit Assessment Details"
    >
      <div className="space-y-5">
        {/* Risky field warning */}
        {showRiskyWarning && (
          <div className="flex items-start gap-3 bg-[#fffbeb] border border-[#fde68a] rounded-xl p-3">
            <AlertTriangle
              className="w-4 h-4 text-brand-gold-dark flex-shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <p className="text-xs font-sans text-brand-gold-dark leading-relaxed">
              {assessment.attempt_count} student
              {assessment.attempt_count === 1 ? "" : "s"} have already started
              or completed this assessment. Changing{" "}
              {[...dirtyRiskyFields].join(", ")} may affect their experience.
            </p>
          </div>
        )}

        {/* Closed notice */}
        {isClosed && (
          <div className="bg-brand-border-soft border border-brand-border rounded-xl p-3">
            <p className="text-xs font-sans text-brand-body">
              This assessment is closed. Only the title and instructions can be
              edited.
            </p>
          </div>
        )}

        {/* Title */}
        <div>
          <label
            htmlFor="edit-title"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Title
          </label>
          <input
            id="edit-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
          />
        </div>

        {/* Instructions */}
        <div>
          <label
            htmlFor="edit-instructions"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Instructions{" "}
            <span className="font-normal text-brand-muted">(optional)</span>
          </label>
          <textarea
            id="edit-instructions"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
          />
        </div>

        {/* Deadline */}
        <div>
          <label
            htmlFor="edit-deadline"
            className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
          >
            Deadline{" "}
            <span className="font-normal text-brand-muted">(optional)</span>
          </label>
          <input
            id="edit-deadline"
            type="datetime-local"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
          />
        </div>

        {/* Risky fields — hidden for CLOSED assessments */}
        {!isClosed && (
          <>
            {/* Question count */}
            <div>
              <label
                htmlFor="edit-question-count"
                className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
              >
                Questions per attempt
                {hasAttempts && (
                  <span className="ml-1.5 text-[10px] font-bold text-brand-gold-dark bg-[#fffbeb] border border-[#fde68a] rounded px-1.5 py-0.5">
                    ⚠ risky
                  </span>
                )}
              </label>
              <input
                id="edit-question-count"
                type="number"
                min={1}
                value={questionCount}
                onChange={(e) => {
                  setQuestionCount(e.target.value);
                  markRisky("question_count");
                }}
                className="w-32 border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
              />
            </div>

            {/* Time limit */}
            <div>
              <label
                htmlFor="edit-time-limit"
                className="block text-xs font-sans font-semibold text-brand-ink mb-1.5"
              >
                Time limit (minutes){" "}
                <span className="font-normal text-brand-muted">
                  — 0 = unlimited
                </span>
                {hasAttempts && (
                  <span className="ml-1.5 text-[10px] font-bold text-brand-gold-dark bg-[#fffbeb] border border-[#fde68a] rounded px-1.5 py-0.5">
                    ⚠ risky
                  </span>
                )}
              </label>
              <input
                id="edit-time-limit"
                type="number"
                min={0}
                value={timeLimitMinutes}
                onChange={(e) => {
                  setTimeLimitMinutes(parseInt(e.target.value, 10) || 0);
                  markRisky("time_limit_minutes");
                }}
                className="w-32 border border-brand-border rounded-lg px-3 py-2 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
              />
            </div>
          </>
        )}

        {/* Error */}
        {errorMsg && (
          <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-3">
            <p className="text-xs font-sans text-brand-red">{errorMsg}</p>
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
            onClick={() => void handleSave()}
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
