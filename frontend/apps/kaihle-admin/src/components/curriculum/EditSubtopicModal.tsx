/**
 * EditSubtopicModal - Modal for editing an existing subtopic.
 */

import { useEffect, useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2 } from "lucide-react";

interface Subtopic {
  id: string;
  curriculum_topic_id: string;
  name: string;
  canonical_code: string | null;
  learning_objective: string;
  description: string | null;
  keywords: string[];
  bloom_taxonomy_level: string | null;
  difficulty_level: number | null;
  estimated_minutes: number | null;
  sequence_order: number | null;
  is_active: boolean;
}

interface EditSubtopicModalProps {
  subtopic: Subtopic | null;
  topicName: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    id: string;
    name?: string;
    learningObjective?: string;
    canonicalCode?: string;
    description?: string;
    keywords?: string[];
    bloomTaxonomyLevel?: string;
    difficultyLevel?: number;
    estimatedMinutes?: number;
    sequenceOrder?: number;
    isActive?: boolean;
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

export function EditSubtopicModal({
  subtopic,
  topicName,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: EditSubtopicModalProps) {
  const [name, setName] = useState("");
  const [learningObjective, setLearningObjective] = useState("");
  const [canonicalCode, setCanonicalCode] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [bloomTaxonomyLevel, setBloomTaxonomyLevel] = useState<string>("");
  const [difficultyLevel, setDifficultyLevel] = useState<string>("");
  const [estimatedMinutes, setEstimatedMinutes] = useState<string>("");
  const [sequenceOrder, setSequenceOrder] = useState<string>("");
  const [isActive, setIsActive] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (subtopic) {
      setName(subtopic.name);
      setLearningObjective(subtopic.learning_objective);
      setCanonicalCode(subtopic.canonical_code ?? "");
      setDescription(subtopic.description ?? "");
      setKeywords(subtopic.keywords.join(", "));
      setBloomTaxonomyLevel(subtopic.bloom_taxonomy_level ?? "");
      setDifficultyLevel(subtopic.difficulty_level?.toString() ?? "");
      setEstimatedMinutes(subtopic.estimated_minutes?.toString() ?? "");
      setSequenceOrder(subtopic.sequence_order?.toString() ?? "");
      setIsActive(subtopic.is_active);
      setFieldErrors({});
    }
  }, [subtopic]);

  const handleClose = () => {
    if (!isSubmitting) {
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
    if (!subtopic || !validate() || isSubmitting) return;

    const data: Parameters<typeof onSubmit>[0] = { id: subtopic.id };
    const newKeywords = keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);

    if (name.trim() !== subtopic.name) data.name = name.trim();
    if (learningObjective.trim() !== subtopic.learning_objective) {
      data.learningObjective = learningObjective.trim();
    }
    if (canonicalCode.trim() !== (subtopic.canonical_code ?? "")) {
      data.canonicalCode = canonicalCode.trim() || undefined;
    }
    if (description.trim() !== (subtopic.description ?? "")) {
      data.description = description.trim() || undefined;
    }
    if (JSON.stringify(newKeywords) !== JSON.stringify(subtopic.keywords)) {
      data.keywords = newKeywords;
    }
    if (bloomTaxonomyLevel !== (subtopic.bloom_taxonomy_level ?? "")) {
      data.bloomTaxonomyLevel = bloomTaxonomyLevel || undefined;
    }
    if (difficultyLevel !== (subtopic.difficulty_level?.toString() ?? "")) {
      data.difficultyLevel = difficultyLevel
        ? parseInt(difficultyLevel, 10)
        : undefined;
    }
    if (estimatedMinutes !== (subtopic.estimated_minutes?.toString() ?? "")) {
      data.estimatedMinutes = estimatedMinutes
        ? parseInt(estimatedMinutes, 10)
        : undefined;
    }
    if (sequenceOrder !== (subtopic.sequence_order?.toString() ?? "")) {
      data.sequenceOrder = sequenceOrder
        ? parseInt(sequenceOrder, 10)
        : undefined;
    }
    if (isActive !== subtopic.is_active) data.isActive = isActive;

    await onSubmit(data);
  };

  if (!subtopic) return null;

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Edit subtopic"
      description={topicName ? `Under: ${topicName}` : "Edit subtopic details"}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Name */}
        <div>
          <label
            htmlFor="edit-subtopic-name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-subtopic-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Solving Linear Equations"
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
            htmlFor="edit-learning-objective"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Learning objective <span className="text-red-500">*</span>
          </label>
          <textarea
            id="edit-learning-objective"
            value={learningObjective}
            onChange={(e) => setLearningObjective(e.target.value)}
            rows={2}
            placeholder="Students will be able to... (minimum 10 characters)"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
          {fieldErrors.learningObjective && (
            <p className="mt-1 text-xs text-red-500">
              {fieldErrors.learningObjective}
            </p>
          )}
        </div>

        {/* Two column layout */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="edit-canonical-code"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Canonical code
            </label>
            <input
              id="edit-canonical-code"
              type="text"
              value={canonicalCode}
              onChange={(e) => setCanonicalCode(e.target.value.toUpperCase())}
              placeholder="e.g., 7Ma1.2"
              className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              disabled={isSubmitting}
            />
          </div>
          <div>
            <label
              htmlFor="edit-subtopic-sequence"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Sequence order
            </label>
            <input
              id="edit-subtopic-sequence"
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
            htmlFor="edit-subtopic-description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description
          </label>
          <textarea
            id="edit-subtopic-description"
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
            htmlFor="edit-subtopic-keywords"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Keywords
          </label>
          <input
            id="edit-subtopic-keywords"
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., linear, equation, variable (comma-separated)"
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
          <div>
            <label
              htmlFor="edit-difficulty-level"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Difficulty (1-5)
            </label>
            <div className="flex items-center gap-2">
              <input
                id="edit-difficulty-level"
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
          <div>
            <label
              htmlFor="edit-estimated-minutes"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Estimated minutes
            </label>
            <input
              id="edit-estimated-minutes"
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

        {/* Active Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="edit-subtopic-active"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="edit-subtopic-active"
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
