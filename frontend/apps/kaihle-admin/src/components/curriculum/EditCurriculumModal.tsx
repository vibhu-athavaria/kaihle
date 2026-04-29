/**
 * EditCurriculumModal - Modal for editing an existing curriculum board.
 *
 * Fields: Name, Code, Description, Country, Active toggle
 */

import { useEffect, useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2 } from "lucide-react";

interface Curriculum {
  id: string;
  name: string;
  code: string;
  description: string | null;
  country: string | null;
  is_active: boolean;
}

interface EditCurriculumModalProps {
  curriculum: Curriculum | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    id: string;
    name?: string;
    code?: string;
    description?: string;
    country?: string;
    is_active?: boolean;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export function EditCurriculumModal({
  curriculum,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: EditCurriculumModalProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [country, setCountry] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Populate form when curriculum changes
  useEffect(() => {
    if (curriculum) {
      setName(curriculum.name);
      setCode(curriculum.code);
      setDescription(curriculum.description ?? "");
      setCountry(curriculum.country ?? "");
      setIsActive(curriculum.is_active);
      setFieldErrors({});
    }
  }, [curriculum]);

  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!name.trim()) {
      errors.name = "Name is required";
    } else if (name.length > 200) {
      errors.name = "Name must be 200 characters or less";
    }

    if (!code.trim()) {
      errors.code = "Code is required";
    } else if (code.length > 50) {
      errors.code = "Code must be 50 characters or less";
    } else if (!/^[a-z0-9_-]+$/.test(code)) {
      errors.code =
        "Code must be lowercase letters, numbers, hyphens, or underscores";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curriculum || !validate() || isSubmitting) return;

    const data: {
      id: string;
      name?: string;
      code?: string;
      description?: string;
      country?: string;
      is_active?: boolean;
    } = { id: curriculum.id };

    // Only include changed fields
    if (name.trim() !== curriculum.name) data.name = name.trim();
    if (code.trim() !== curriculum.code) data.code = code.trim();
    if (description.trim() !== (curriculum.description ?? "")) {
      data.description = description.trim() || undefined;
    }
    if (country.trim() !== (curriculum.country ?? "")) {
      data.country = country.trim() || undefined;
    }
    if (isActive !== curriculum.is_active) data.is_active = isActive;

    await onSubmit(data);
  };

  if (!curriculum) return null;

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Edit curriculum"
      description="Update curriculum details."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Name */}
        <div>
          <label
            htmlFor="edit-curriculum-name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-curriculum-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
            placeholder="e.g., Cambridge IGCSE"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          {fieldErrors.name && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.name}</p>
          )}
        </div>

        {/* Code */}
        <div>
          <label
            htmlFor="edit-curriculum-code"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Code <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-curriculum-code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toLowerCase())}
            maxLength={50}
            placeholder="e.g., igcse"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-gray-500">
            Unique identifier, lowercase, no spaces
          </p>
          {fieldErrors.code && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.code}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label
            htmlFor="edit-curriculum-description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description
          </label>
          <textarea
            id="edit-curriculum-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Optional description of the curriculum"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Country */}
        <div>
          <label
            htmlFor="edit-curriculum-country"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Country
          </label>
          <input
            id="edit-curriculum-country"
            type="text"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="Leave blank for international boards"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Active Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="edit-curriculum-active"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="edit-curriculum-active"
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
