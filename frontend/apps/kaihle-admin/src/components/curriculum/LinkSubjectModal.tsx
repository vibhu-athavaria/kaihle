/**
 * LinkSubjectModal - Modal for linking a subject to a curriculum.
 *
 * Fields: Subject select (required), Is core toggle (default true), Sort order (optional)
 */

import { useState, useMemo, useRef } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2, Search, Check } from "lucide-react";

interface Subject {
  id: string;
  name: string;
  code: string;
}

interface LinkSubjectModalProps {
  curriculumId: string | null;
  availableSubjects: Subject[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    curriculumId: string;
    subjectId: string;
    isCore: boolean;
    sortOrder?: number;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export function LinkSubjectModal({
  curriculumId,
  availableSubjects,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: LinkSubjectModalProps) {
  const [subjectId, setSubjectId] = useState<string>("");
  const [subjectSearch, setSubjectSearch] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [isCore, setIsCore] = useState(true);
  const [sortOrder, setSortOrder] = useState<string>("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const searchRef = useRef<HTMLInputElement>(null);

  const resetForm = () => {
    setSubjectId("");
    setSubjectSearch("");
    setShowDropdown(false);
    setIsCore(true);
    setSortOrder("");
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

    if (!subjectId) {
      errors.subjectId = "Please select a subject";
    }

    if (
      sortOrder &&
      (isNaN(parseInt(sortOrder, 10)) || parseInt(sortOrder, 10) < 0)
    ) {
      errors.sortOrder = "Sort order must be a positive number";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curriculumId || !validate() || isSubmitting) return;

    await onSubmit({
      curriculumId,
      subjectId,
      isCore,
      sortOrder: sortOrder ? parseInt(sortOrder, 10) : undefined,
    });

    resetForm();
  };

  const selectedSubject = useMemo(
    () => availableSubjects.find((s) => s.id === subjectId),
    [availableSubjects, subjectId],
  );

  const filteredSubjects = useMemo(() => {
    const sorted = [...availableSubjects].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
    if (!subjectSearch.trim()) return sorted;
    const q = subjectSearch.toLowerCase();
    return sorted.filter(
      (s) =>
        s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q),
    );
  }, [availableSubjects, subjectSearch]);

  const handleSelectSubject = (subject: Subject) => {
    setSubjectId(subject.id);
    setSubjectSearch(subject.name);
    setShowDropdown(false);
    setFieldErrors((prev) => ({ ...prev, subjectId: "" }));
  };

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title="Add subject to curriculum"
      description="Link an existing subject to this curriculum."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        {/* Subject Typeahead */}
        <div className="relative">
          <label
            htmlFor="subject-search"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Subject <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              id="subject-search"
              ref={searchRef}
              type="text"
              value={subjectSearch}
              onChange={(e) => {
                setSubjectSearch(e.target.value);
                setSubjectId("");
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
              placeholder="Search subjects..."
              autoComplete="off"
              className="w-full bg-white border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              disabled={isSubmitting}
            />
            {selectedSubject && (
              <Check className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-primary" />
            )}
          </div>
          {showDropdown && filteredSubjects.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
              {filteredSubjects.map((subject) => (
                <li key={subject.id}>
                  <button
                    type="button"
                    onMouseDown={() => handleSelectSubject(subject)}
                    className={`w-full text-left px-3 py-2 text-sm font-['Inter'] hover:bg-gray-50 transition-colors ${
                      subject.id === subjectId
                        ? "text-brand-primary font-medium bg-brand-primary/5"
                        : "text-gray-900"
                    }`}
                  >
                    {subject.name}{" "}
                    <span className="text-gray-400 text-xs">
                      ({subject.code})
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {showDropdown &&
            subjectSearch.trim() &&
            filteredSubjects.length === 0 && (
              <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2">
                <p className="text-sm text-gray-500">No subjects match</p>
              </div>
            )}
          {availableSubjects.length === 0 && (
            <p className="mt-1 text-xs text-amber-600">
              No available subjects to link. All subjects are already linked to
              this curriculum.
            </p>
          )}
          {fieldErrors.subjectId && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.subjectId}</p>
          )}
        </div>

        {/* Is Core Toggle */}
        <div className="flex items-center gap-3">
          <input
            id="is-core"
            type="checkbox"
            checked={isCore}
            onChange={(e) => setIsCore(e.target.checked)}
            className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
            disabled={isSubmitting}
          />
          <label
            htmlFor="is-core"
            className="text-sm font-medium text-gray-700"
          >
            Core subject
          </label>
        </div>
        <p className="text-xs text-gray-500 -mt-3 ml-7">
          Core subjects are required for all students in this curriculum.
        </p>

        {/* Sort Order */}
        <div>
          <label
            htmlFor="sort-order"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Sort order
          </label>
          <input
            id="sort-order"
            type="number"
            min={0}
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            placeholder="Auto-assigned if blank"
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-gray-500">
            Display order within the curriculum (0 = first). Leave blank for
            auto-assignment.
          </p>
          {fieldErrors.sortOrder && (
            <p className="mt-1 text-xs text-red-500">{fieldErrors.sortOrder}</p>
          )}
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
            disabled={isSubmitting || availableSubjects.length === 0}
            className="px-4 py-2 bg-brand-primary text-white rounded-full text-sm font-medium font-['Inter'] hover:bg-brand-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Adding...
              </>
            ) : (
              "Add subject"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
