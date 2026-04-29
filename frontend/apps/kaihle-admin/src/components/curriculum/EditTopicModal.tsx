/**
 * EditTopicModal - Modal for editing a curriculum topic placement.
 *
 * Fields: Standard code, Sequence order, Learning objectives, Recommended weeks, Is required, Is active
 */

import { useEffect, useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2 } from "lucide-react";

interface Topic {
  curriculum_topic_id: string;
  topic_id: string;
  name: string;
  canonical_code: string | null;
  standard_code: string | null;
  sequence_order: number | null;
  learning_objectives: string[];
  recommended_weeks: number | null;
  is_required: boolean;
  is_active: boolean;
}

interface EditTopicModalProps {
  topic: Topic | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    ctId: string;
    standardCode?: string;
    sequenceOrder?: number;
    learningObjectives?: string[];
    recommendedWeeks?: number;
    isRequired?: boolean;
    isActive?: boolean;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export function EditTopicModal({
  topic,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: EditTopicModalProps) {
  const [standardCode, setStandardCode] = useState("");
  const [sequenceOrder, setSequenceOrder] = useState<string>("");
  const [learningObjectives, setLearningObjectives] = useState("");
  const [recommendedWeeks, setRecommendedWeeks] = useState<string>("");
  const [isRequired, setIsRequired] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (topic) {
      setStandardCode(topic.standard_code ?? "");
      setSequenceOrder(topic.sequence_order?.toString() ?? "");
      setLearningObjectives(topic.learning_objectives.join("\n"));
      setRecommendedWeeks(topic.recommended_weeks?.toString() ?? "");
      setIsRequired(topic.is_required);
      setIsActive(topic.is_active);
      setFieldErrors({});
    }
  }, [topic]);

  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (
      sequenceOrder &&
      (isNaN(parseInt(sequenceOrder, 10)) || parseInt(sequenceOrder, 10) < 1)
    ) {
      errors.sequenceOrder = "Sequence order must be a positive number";
    }

    if (
      recommendedWeeks &&
      (isNaN(parseInt(recommendedWeeks, 10)) ||
        parseInt(recommendedWeeks, 10) < 1)
    ) {
      errors.recommendedWeeks = "Recommended weeks must be a positive number";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic || !validate() || isSubmitting) return;

    const data: Parameters<typeof onSubmit>[0] = {
      ctId: topic.curriculum_topic_id,
    };

    const newObjectives = learningObjectives
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    if (standardCode.trim() !== (topic.standard_code ?? "")) {
      data.standardCode = standardCode.trim() || undefined;
    }
    if (sequenceOrder !== (topic.sequence_order?.toString() ?? "")) {
      data.sequenceOrder = sequenceOrder
        ? parseInt(sequenceOrder, 10)
        : undefined;
    }
    if (
      JSON.stringify(newObjectives) !==
      JSON.stringify(topic.learning_objectives)
    ) {
      data.learningObjectives = newObjectives;
    }
    if (recommendedWeeks !== (topic.recommended_weeks?.toString() ?? "")) {
      data.recommendedWeeks = recommendedWeeks
        ? parseInt(recommendedWeeks, 10)
        : undefined;
    }
    if (isRequired !== topic.is_required) data.isRequired = isRequired;
    if (isActive !== topic.is_active) data.isActive = isActive;

    await onSubmit(data);
  };

  if (!topic) return null;

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Edit topic placement"
      description={`${topic.name}${topic.canonical_code ? ` (${topic.canonical_code})` : ""}`}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Standard Code */}
        <div>
          <label
            htmlFor="edit-standard-code"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Standard code
          </label>
          <input
            id="edit-standard-code"
            type="text"
            value={standardCode}
            onChange={(e) => setStandardCode(e.target.value)}
            placeholder="e.g., 7Ma1"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Sequence Order */}
        <div>
          <label
            htmlFor="edit-sequence-order"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Sequence order
          </label>
          <input
            id="edit-sequence-order"
            type="number"
            min={1}
            value={sequenceOrder}
            onChange={(e) => setSequenceOrder(e.target.value)}
            placeholder="Auto-assigned if blank"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          {fieldErrors.sequenceOrder && (
            <p className="mt-1 text-xs text-red-500">
              {fieldErrors.sequenceOrder}
            </p>
          )}
        </div>

        {/* Learning Objectives */}
        <div>
          <label
            htmlFor="edit-learning-objectives"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Learning objectives
          </label>
          <textarea
            id="edit-learning-objectives"
            value={learningObjectives}
            onChange={(e) => setLearningObjectives(e.target.value)}
            rows={3}
            placeholder="Enter one objective per line"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-gray-500">One objective per line</p>
        </div>

        {/* Recommended Weeks */}
        <div>
          <label
            htmlFor="edit-recommended-weeks"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Recommended weeks
          </label>
          <input
            id="edit-recommended-weeks"
            type="number"
            min={1}
            value={recommendedWeeks}
            onChange={(e) => setRecommendedWeeks(e.target.value)}
            placeholder="e.g., 2"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          {fieldErrors.recommendedWeeks && (
            <p className="mt-1 text-xs text-red-500">
              {fieldErrors.recommendedWeeks}
            </p>
          )}
        </div>

        {/* Required Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="edit-is-required"
            type="checkbox"
            checked={isRequired}
            onChange={(e) => setIsRequired(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="edit-is-required"
            className="text-sm font-medium text-gray-700"
          >
            Required topic
          </label>
        </div>

        {/* Active Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="edit-is-active"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="edit-is-active"
            className="text-sm font-medium text-gray-700"
          >
            Active
          </label>
        </div>

        {/* Error from API */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 justify-end pt-4 border-t border-gray-100">
          <button
            type="button"
            onClick={handleClose}
            disabled={isSubmitting}
            className="px-4 py-2 border border-gray-200 text-gray-700 rounded-full text-sm font-medium font-['Inter'] hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-4 py-2 bg-brand-primary text-white rounded-full text-sm font-medium font-['Inter'] hover:bg-brand-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save changes"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
