/**
 * AddSubtopicModal - Modal for creating a new subtopic.
 *
 * Fields: Name, Learning objective (required, min 10 chars), Description, Keywords,
 * Bloom's taxonomy level, Difficulty level (1-5), Estimated minutes, Sequence order
 */

import { useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2 } from "lucide-react";

interface AddSubtopicModalProps {
  curriculumTopicId: string | null;
  topicName: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    ctId: string;
    name: string;
    learningObjective: string;
    canonicalCode?: string;
    description?: string;
    keywords: string[];
    bloomTaxonomyLevel?: string;
    difficultyLevel?: number;
    estimatedMinutes?: number;
    sequenceOrder?: number;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

const BLOOM_LEVELS = [
  { value: "Remember", label: "Remember", color: "bg-blue-100 text-blue-800" },
  {
    value: "Understand",
    label: "Understand",
    color: "bg-green-100 text-green-800",
  },
  { value: "Apply", label: "Apply", color: "bg-yellow-100 text-yellow-800" },
  {
    value: "Analyse",
    label: "Analyse",
    color: "bg-orange-100 text-orange-800",
  },
  { value: "Evaluate", label: "Evaluate", color: "bg-red-100 text-red-800" },
  { value: "Create", label: "Create", color: "bg-purple-100 text-purple-800" },
];

export function AddSubtopicModal({
  curriculumTopicId,
  topicName,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: AddSubtopicModalProps) {
  const [name, setName] = useState("");
  const [learningObjective, setLearningObjective] = useState("");
  const [canonicalCode, setCanonicalCode] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [bloomTaxonomyLevel, setBloomTaxonomyLevel] = useState<string>("");
  const [difficultyLevel, setDifficultyLevel] = useState<string>("");
  const [estimatedMinutes, setEstimatedMinutes] = useState<string>("");
  const [sequenceOrder, setSequenceOrder] = useState<string>("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const resetForm = () => {
    setName("");
    setLearningObjective("");
    setCanonicalCode("");
    setDescription("");
    setKeywords("");
    setBloomTaxonomyLevel("");
    setDifficultyLevel("");
    setEstimatedMinutes("");
    setSequenceOrder("");
    setFieldErrors({});
  };

  const handleClose = () => {
    if (!isSubmitting) {
      resetForm();
      onClose();
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!name.trim()) {
      errors.name = "Name is required";
    }

    if (!learningObjective.trim()) {
      errors.learningObjective = "Learning objective is required";
    } else if (learningObjective.trim().length < 10) {
      errors.learningObjective =
        "Learning objective must be at least 10 characters";
    }

    if (difficultyLevel) {
      const level = parseInt(difficultyLevel, 10);
      if (isNaN(level) || level < 1 || level > 5) {
        errors.difficultyLevel = "Difficulty level must be between 1 and 5";
      }
    }

    if (
      estimatedMinutes &&
      (isNaN(parseInt(estimatedMinutes, 10)) ||
        parseInt(estimatedMinutes, 10) < 1)
    ) {
      errors.estimatedMinutes = "Estimated minutes must be a positive number";
    }

    if (
      sequenceOrder &&
      (isNaN(parseInt(sequenceOrder, 10)) || parseInt(sequenceOrder, 10) < 1)
    ) {
      errors.sequenceOrder = "Sequence order must be a positive number";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curriculumTopicId || !validate() || isSubmitting) return;

    await onSubmit({
      ctId: curriculumTopicId,
      name: name.trim(),
      learningObjective: learningObjective.trim(),
      canonicalCode: canonicalCode.trim() || undefined,
      description: description.trim() || undefined,
      keywords: keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean),
      bloomTaxonomyLevel: bloomTaxonomyLevel || undefined,
      difficultyLevel: difficultyLevel
        ? parseInt(difficultyLevel, 10)
        : undefined,
      estimatedMinutes: estimatedMinutes
        ? parseInt(estimatedMinutes, 10)
        : undefined,
      sequenceOrder: sequenceOrder ? parseInt(sequenceOrder, 10) : undefined,
    });

    resetForm();
  };

  // Auto-generate code from name
  const handleNameBlur = () => {
    if (!canonicalCode && name) {
      const autoCode = name
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, ".")
        .replace(/^\.+|\.+$/g, "")
        .substring(0, 50);
      setCanonicalCode(autoCode);
    }
  };

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Add subtopic"
      description={topicName ? `Under: ${topicName}` : "Add a new subtopic"}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Name */}
        <div>
          <label
            htmlFor="subtopic-name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="subtopic-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={handleNameBlur}
            placeholder="e.g., Solving Linear Equations with One Variable"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          {fieldErrors.name && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.name}</p>
          )}
        </div>

        {/* Learning Objective */}
        <div>
          <label
            htmlFor="learning-objective"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Learning objective <span className="text-red-500">*</span>
          </label>
          <textarea
            id="learning-objective"
            value={learningObjective}
            onChange={(e) => setLearningObjective(e.target.value)}
            rows={2}
            placeholder="Students will be able to... (minimum 10 characters)"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-gray-500">
            This is fed to the LLM for content generation. Be specific and
            actionable.
          </p>
          {fieldErrors.learningObjective && (
            <p className="mt-1 text-xs text-red-500">
              {fieldErrors.learningObjective}
            </p>
          )}
        </div>

        {/* Two column layout */}
        <div className="grid grid-cols-2 gap-4">
          {/* Canonical Code */}
          <div>
            <label
              htmlFor="canonical-code"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Canonical code
            </label>
            <input
              id="canonical-code"
              type="text"
              value={canonicalCode}
              onChange={(e) => setCanonicalCode(e.target.value.toUpperCase())}
              placeholder="e.g., 7Ma1.2"
              className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              disabled={isSubmitting}
            />
          </div>

          {/* Sequence Order */}
          <div>
            <label
              htmlFor="subtopic-sequence"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Sequence order
            </label>
            <input
              id="subtopic-sequence"
              type="number"
              min={1}
              value={sequenceOrder}
              onChange={(e) => setSequenceOrder(e.target.value)}
              placeholder="Auto"
              className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              disabled={isSubmitting}
            />
            {fieldErrors.sequenceOrder && (
              <p className="mt-1 text-xs text-red-500">
                {fieldErrors.sequenceOrder}
              </p>
            )}
          </div>
        </div>

        {/* Description */}
        <div>
          <label
            htmlFor="subtopic-description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description
          </label>
          <textarea
            id="subtopic-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Optional detailed description"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Keywords */}
        <div>
          <label
            htmlFor="subtopic-keywords"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Keywords
          </label>
          <input
            id="subtopic-keywords"
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., linear, equation, variable, algebra (comma-separated)"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Bloom's Taxonomy */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Bloom&apos;s taxonomy level
          </label>
          <div className="flex flex-wrap gap-2">
            {BLOOM_LEVELS.map((level) => (
              <button
                key={level.value}
                type="button"
                onClick={() => setBloomTaxonomyLevel(level.value)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                  bloomTaxonomyLevel === level.value
                    ? level.color + " ring-2 ring-offset-1 ring-gray-400"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
                disabled={isSubmitting}
              >
                {level.label}
              </button>
            ))}
          </div>
        </div>

        {/* Two column: Difficulty and Time */}
        <div className="grid grid-cols-2 gap-4">
          {/* Difficulty Level */}
          <div>
            <label
              htmlFor="difficulty-level"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Difficulty (1-5)
            </label>
            <div className="flex items-center gap-2">
              <input
                id="difficulty-level"
                type="range"
                min={1}
                max={5}
                value={difficultyLevel || 3}
                onChange={(e) => setDifficultyLevel(e.target.value)}
                className="flex-1"
                disabled={isSubmitting}
              />
              <span className="w-8 text-center font-medium text-gray-700">
                {difficultyLevel || "-"}
              </span>
            </div>
            {fieldErrors.difficultyLevel && (
              <p className="mt-1 text-xs text-red-500">
                {fieldErrors.difficultyLevel}
              </p>
            )}
          </div>

          {/* Estimated Minutes */}
          <div>
            <label
              htmlFor="estimated-minutes"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Estimated minutes
            </label>
            <input
              id="estimated-minutes"
              type="number"
              min={1}
              value={estimatedMinutes}
              onChange={(e) => setEstimatedMinutes(e.target.value)}
              placeholder="e.g., 45"
              className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              disabled={isSubmitting}
            />
            {fieldErrors.estimatedMinutes && (
              <p className="mt-1 text-xs text-red-500">
                {fieldErrors.estimatedMinutes}
              </p>
            )}
          </div>
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
                Creating...
              </>
            ) : (
              "Create subtopic"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
