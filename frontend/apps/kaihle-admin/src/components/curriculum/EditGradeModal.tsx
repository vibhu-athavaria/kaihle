/**
 * EditGradeModal - Modal for editing an existing grade level.
 */

import { useEffect, useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2 } from "lucide-react";

interface Grade {
  id: string;
  name: string;
  level: number;
  description: string | null;
  is_active: boolean;
}

interface EditGradeModalProps {
  grade: Grade | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    id: string;
    name?: string;
    level?: number;
    description?: string;
    is_active?: boolean;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export function EditGradeModal({
  grade,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: EditGradeModalProps) {
  const [name, setName] = useState("");
  const [level, setLevel] = useState<string>("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (grade) {
      setName(grade.name);
      setLevel(grade.level.toString());
      setDescription(grade.description ?? "");
      setIsActive(grade.is_active);
      setFieldErrors({});
    }
  }, [grade]);

  const handleClose = () => {
    if (!isSubmitting) {
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
    if (!grade || !validate() || isSubmitting) return;

    const data: {
      id: string;
      name?: string;
      level?: number;
      description?: string;
      is_active?: boolean;
    } = { id: grade.id };

    if (name.trim() !== grade.name) data.name = name.trim();
    if (parseInt(level, 10) !== grade.level) data.level = parseInt(level, 10);
    if (description.trim() !== (grade.description ?? "")) {
      data.description = description.trim() || undefined;
    }
    if (isActive !== grade.is_active) data.is_active = isActive;

    await onSubmit(data);
  };

  if (!grade) return null;

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Edit grade"
      description="Update grade level details."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Name */}
        <div>
          <label
            htmlFor="edit-grade-name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-grade-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
            placeholder="e.g., Grade 7"
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
            htmlFor="edit-grade-level"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Level <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-grade-level"
            type="number"
            min={1}
            max={13}
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            placeholder="1-13"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-gray-500">
            Numeric level from 1 to 13
          </p>
          {fieldErrors.level && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.level}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label
            htmlFor="edit-grade-description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description
          </label>
          <textarea
            id="edit-grade-description"
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
            id="edit-grade-active"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="edit-grade-active"
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
