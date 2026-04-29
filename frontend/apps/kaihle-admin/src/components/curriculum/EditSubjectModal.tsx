/**
 * EditSubjectModal - Modal for editing an existing subject.
 */

import { useEffect, useState } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2, BookOpen, AlertCircle } from "lucide-react";
import * as LucideIcons from "lucide-react";

interface Subject {
  id: string;
  name: string;
  code: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  is_active: boolean;
}

interface EditSubjectModalProps {
  subject: Subject | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    id: string;
    name?: string;
    code?: string;
    description?: string;
    icon?: string;
    color?: string;
    is_active?: boolean;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

// Brand palette colors
const BRAND_COLORS = [
  { name: "Primary", value: "#1a5c38" },
  { name: "Secondary", value: "#2d7a4f" },
  { name: "Blue", value: "#2563eb" },
  { name: "Purple", value: "#7c3aed" },
  { name: "Orange", value: "#ea580c" },
  { name: "Pink", value: "#db2777" },
  { name: "Teal", value: "#0d9488" },
  { name: "Gray", value: "#6b7280" },
];

export function EditSubjectModal({
  subject,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: EditSubjectModalProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState("");
  const [color, setColor] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [iconError, setIconError] = useState(false);

  useEffect(() => {
    if (subject) {
      setName(subject.name);
      setCode(subject.code);
      setDescription(subject.description ?? "");
      setIcon(subject.icon ?? "");
      setColor(subject.color ?? "");
      setIsActive(subject.is_active);
      setFieldErrors({});
      setIconError(false);
    }
  }, [subject]);

  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!name.trim()) {
      errors.name = "Name is required";
    } else if (name.length > 100) {
      errors.name = "Name must be 100 characters or less";
    }

    if (!code.trim()) {
      errors.code = "Code is required";
    } else if (code.length > 20) {
      errors.code = "Code must be 20 characters or less";
    } else if (!/^[A-Z0-9_]+$/.test(code)) {
      errors.code = "Code must be uppercase letters, numbers, or underscores";
    }

    if (color && !/^#[0-9A-Fa-f]{6}$/.test(color)) {
      errors.color = "Color must be a valid hex code";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject || !validate() || isSubmitting) return;

    const data: {
      id: string;
      name?: string;
      code?: string;
      description?: string;
      icon?: string;
      color?: string;
      is_active?: boolean;
    } = { id: subject.id };

    if (name.trim() !== subject.name) data.name = name.trim();
    if (code.trim() !== subject.code) data.code = code.trim();
    if (description.trim() !== (subject.description ?? "")) {
      data.description = description.trim() || undefined;
    }
    if (icon.trim() !== (subject.icon ?? "")) {
      data.icon = icon.trim() || undefined;
    }
    if (color.trim() !== (subject.color ?? "")) {
      data.color = color.trim() || undefined;
    }
    if (isActive !== subject.is_active) data.is_active = isActive;

    await onSubmit(data);
  };

  const handleIconChange = (value: string) => {
    setIcon(value);
    setIconError(false);
    if (value) {
      const iconName = value as keyof typeof LucideIcons;
      if (!(iconName in LucideIcons)) {
        setIconError(true);
      }
    }
  };

  const IconPreview =
    icon && !iconError
      ? (LucideIcons[icon as keyof typeof LucideIcons] as React.ComponentType<{
          className?: string;
        }>)
      : null;

  if (!subject) return null;

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Edit subject"
      description="Update subject details."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Name */}
        <div>
          <label
            htmlFor="edit-subject-name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-subject-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            placeholder="e.g., Mathematics"
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
            htmlFor="edit-subject-code"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Code <span className="text-red-500">*</span>
          </label>
          <input
            id="edit-subject-code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            maxLength={20}
            placeholder="e.g., MATH"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          {fieldErrors.code && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.code}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label
            htmlFor="edit-subject-description"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Description
          </label>
          <textarea
            id="edit-subject-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Optional description"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
            disabled={isSubmitting}
          />
        </div>

        {/* Icon */}
        <div>
          <label
            htmlFor="edit-subject-icon"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Icon
          </label>
          <div className="flex items-center gap-3">
            <input
              id="edit-subject-icon"
              type="text"
              value={icon}
              onChange={(e) => handleIconChange(e.target.value)}
              placeholder="e.g., BookOpen, Calculator"
              className="flex-1 bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              disabled={isSubmitting}
            />
            <div className="w-10 h-10 rounded-lg border border-gray-200 flex items-center justify-center bg-gray-50">
              {IconPreview ? (
                <IconPreview className="w-5 h-5 text-gray-600" />
              ) : (
                <BookOpen className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </div>
          {iconError && (
            <p className="mt-1 text-xs text-amber-600 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              Icon not found in Lucide library
            </p>
          )}
        </div>

        {/* Color */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Color
          </label>
          <div className="flex flex-wrap gap-2">
            {BRAND_COLORS.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setColor(c.value)}
                className={`w-8 h-8 rounded-full border-2 transition-all ${
                  color === c.value
                    ? "border-gray-900 scale-110"
                    : "border-transparent hover:scale-105"
                }`}
                style={{ backgroundColor: c.value }}
                title={c.name}
                disabled={isSubmitting}
              />
            ))}
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={color || "#1a5c38"}
                onChange={(e) => setColor(e.target.value)}
                className="w-8 h-8 rounded-full border-0 cursor-pointer"
                disabled={isSubmitting}
              />
              <input
                type="text"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                placeholder="#1a5c38"
                className="w-24 bg-white border border-gray-200 rounded-lg px-2 py-1 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isSubmitting}
              />
            </div>
          </div>
          {fieldErrors.color && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.color}</p>
          )}
        </div>

        {/* Active Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="edit-subject-active"
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="edit-subject-active"
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
