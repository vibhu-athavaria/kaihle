/**
 * CreateGradeModal - Modal for creating a new grade level.
 *
 * Fields: Name (required, max 50), Level (required, 1-13), Description (optional), Active toggle
 */

import { useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2 } from "lucide-react";

interface CreateGradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    name: string;
    level: number;
    description?: string;
    is_active: boolean;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export function CreateGradeModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: CreateGradeModalProps) {
  const [name, setName] = useState("");
  const [level, setLevel] = useState<string>("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const resetForm = () => {
    setName("");
    setLevel("");
    setDescription("");
    setIsActive(true);
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
    } else if (name.length > 50) {
      errors.name = "Name must be 50 characters or less";
    }

    if (level === "") {
      errors.level = "Level is required";
    } else {
      const levelNum = parseInt(level, 10);
      if (isNaN(levelNum) || levelNum < 1 || levelNum > 13) {
        errors.level = "Level must be between 1 and 13";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate() || isSubmitting) return;

    await onSubmit({
      name: name.trim(),
      level: parseInt(level, 10),
      description: description.trim() || undefined,
      is_active: isActive,
    });

    resetForm();
  };

  // Auto-populate name from level
  const handleLevelChange = (value: string) => {
    setLevel(value);
    if (value && !name) {
      setName(`Grade ${value}`);
    }
  };

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Create grade"
      description="Add a new grade level to the platform."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Name */}
        <div>
          <label
            htmlFor="grade-name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="grade-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
            placeholder="e.g., Grade 7, Year 9, Form 3"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          {fieldErrors.name && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.name}</p>
          )}
        </div>

        {/* Level */}
        <div>
          <label
            htmlFor="grade-level"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Level <span className="text-red-500">*</span>
          </label>
          <input
            id="grade-level"
            type="number"
            min={1}
            max={13}
            value={level}
            onChange={(e) => handleLevelChange(e.target.value)}
            placeholder="1-13"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-gray-500">
            Numeric level from 1 to 13 (must be unique)
          </p>
          {fieldErrors.level && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.level}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label
            htmlFor="grade-description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description
          </label>
          <textarea
            id="grade-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Optional description"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Active Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="grade-active"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="grade-active"
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
                Creating...
              </>
            ) : (
              "Create grade"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
