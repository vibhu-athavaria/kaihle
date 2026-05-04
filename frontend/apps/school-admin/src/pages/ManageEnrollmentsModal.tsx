import { useState, useMemo } from "react";
import { Modal, toast } from "@kaihle/ui";
import {
  useClassStudents,
  useSchoolUsers,
  useUnenrollStudents,
  useEnrollStudents,
} from "../hooks/useSchoolAdmin";

interface ManageEnrollmentsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classId: string;
  className: string | undefined;
}

export function ManageEnrollmentsModal({
  open,
  onOpenChange,
  classId,
  className,
}: ManageEnrollmentsModalProps) {
  const [search, setSearch] = useState("");
  const [pendingRemovals, setPendingRemovals] = useState<Set<string>>(
    new Set(),
  );
  const [pendingAdditions, setPendingAdditions] = useState<Set<string>>(
    new Set(),
  );
  const [isSaving, setIsSaving] = useState(false);

  const { data: enrolled = [] } = useClassStudents(classId);
  const { data: allStudents = [] } = useSchoolUsers("STUDENT");
  const unenroll = useUnenrollStudents(classId);
  const enroll = useEnrollStudents(classId);

  const enrolledIds = useMemo(
    () => new Set(enrolled.map((s) => s.id)),
    [enrolled],
  );

  const notEnrolled = useMemo(
    () =>
      allStudents.filter(
        (s) => !enrolledIds.has(s.id) && !pendingAdditions.has(s.id),
      ),
    [allStudents, enrolledIds, pendingAdditions],
  );

  const filteredEnrolled = enrolled.filter((s) => {
    const full = `${s.first_name} ${s.last_name}`.toLowerCase();
    return full.includes(search.toLowerCase());
  });

  const filteredNotEnrolled = notEnrolled.filter((s) => {
    const full = `${s.first_name} ${s.last_name}`.toLowerCase();
    return full.includes(search.toLowerCase());
  });

  const toggleRemoval = (id: string) => {
    setPendingRemovals((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAddition = (id: string) => {
    setPendingAdditions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Handle removals
      if (pendingRemovals.size > 0) {
        await unenroll.mutateAsync(Array.from(pendingRemovals));
      }
      // Handle additions
      if (pendingAdditions.size > 0) {
        await enroll.mutateAsync({ student_ids: Array.from(pendingAdditions) });
      }
      toast.success("Enrollment changes saved");
      setPendingRemovals(new Set());
      setPendingAdditions(new Set());
      onOpenChange(false);
    } catch {
      toast.error("Failed to save enrollment changes");
    } finally {
      setIsSaving(false);
    }
  };

  const getInitials = (first: string, last: string) =>
    `${first[0] ?? ""}${last[0] ?? ""}`.toUpperCase();

  const avatarColors = [
    "bg-violet-600",
    "bg-red-500",
    "bg-blue-600",
    "bg-amber-600",
    "bg-green-600",
    "bg-cyan-600",
    "bg-purple-600",
  ];
  const getColor = (id: string) =>
    avatarColors[id.charCodeAt(0) % avatarColors.length];

  const displayEnrolled = enrolled.filter((s) => !pendingRemovals.has(s.id));
  const displayAdditions = allStudents.filter((s) =>
    pendingAdditions.has(s.id),
  );

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Manage enrollments"
      description={`${className ?? "Class"} · ${enrolled.length} students enrolled`}
      maxWidth="2xl"
    >
      {/* Search */}
      <div className="relative mb-0">
        <svg
          className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-muted"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search students by name…"
          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary outline-none"
        />
      </div>

      {/* Two-column body */}
      <div className="grid grid-cols-2 mt-4 border border-gray-100 rounded-xl overflow-hidden min-h-[320px] max-h-[400px]">
        {/* Enrolled */}
        <div className="flex flex-col overflow-hidden border-r border-gray-100">
          <div className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-brand-primary border-b border-gray-100 flex items-center gap-2 flex-shrink-0">
            Enrolled
            <span className="bg-brand-light text-brand-primary rounded-full px-2 py-0.5 text-[11px] font-bold">
              {displayEnrolled.length + pendingAdditions.size}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {/* Pending additions shown first */}
            {displayAdditions.map((s) => (
              <div
                key={`add-${s.id}`}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-green-200 bg-green-50 mb-1"
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs flex-shrink-0 ${getColor(s.id)}`}
                >
                  {getInitials(s.first_name, s.last_name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-brand-ink flex items-center gap-1.5">
                    {s.first_name} {s.last_name[0]}.
                    <span className="text-[11px] font-bold bg-green-100 text-green-600 rounded-full px-2 py-0.5">
                      Adding
                    </span>
                  </div>
                  <div className="text-xs text-brand-muted">
                    {s.grade_level ? `Grade ${s.grade_level}` : "No grade"}
                  </div>
                </div>
                <button
                  onClick={() => toggleAddition(s.id)}
                  aria-label="Undo add"
                  className="w-7 h-7 rounded-full bg-brand-light text-brand-primary flex items-center justify-center text-sm font-bold flex-shrink-0 transition-colors"
                >
                  ↩
                </button>
              </div>
            ))}
            {filteredEnrolled.length === 0 && pendingAdditions.size === 0 ? (
              <p className="text-xs text-brand-muted text-center py-8">
                No enrolled students
              </p>
            ) : (
              filteredEnrolled.map((s) => {
                const removing = pendingRemovals.has(s.id);
                return (
                  <div
                    key={s.id}
                    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border mb-1 transition-colors ${
                      removing
                        ? "border-red-200 bg-red-50"
                        : "border-transparent hover:bg-gray-50 hover:border-role-school-border"
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs flex-shrink-0 ${getColor(s.id)}`}
                    >
                      {getInitials(s.first_name, s.last_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-brand-ink flex items-center gap-1.5">
                        {s.first_name} {s.last_name[0]}.
                        {removing && (
                          <span className="text-[11px] font-bold bg-red-100 text-red-500 rounded-full px-2 py-0.5">
                            Removing
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-brand-muted">
                        {s.grade_name ?? "No grade"}
                      </div>
                    </div>
                    <button
                      onClick={() => toggleRemoval(s.id)}
                      aria-label={removing ? "Undo remove" : "Remove student"}
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 ${
                        removing
                          ? "bg-brand-light text-brand-primary"
                          : "bg-red-100 text-red-500"
                      }`}
                    >
                      {removing ? "↩" : "−"}
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Not enrolled */}
        <div className="flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-role-school-muted border-b border-gray-100 flex items-center gap-2 flex-shrink-0">
            Not enrolled
            <span className="bg-gray-100 text-brand-muted rounded-full px-2 py-0.5 text-[11px] font-bold">
              {notEnrolled.length}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {filteredNotEnrolled.length === 0 ? (
              <p className="text-xs text-brand-muted text-center py-8">
                All students enrolled
              </p>
            ) : (
              filteredNotEnrolled.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-transparent hover:bg-gray-50 hover:border-role-school-border mb-1 transition-colors"
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs flex-shrink-0 ${getColor(s.id)}`}
                  >
                    {getInitials(s.first_name, s.last_name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-brand-ink">
                      {s.first_name} {s.last_name[0]}.
                    </div>
                    <div className="text-xs text-brand-muted">
                      {s.grade_level ? `Grade ${s.grade_level}` : "No grade"}
                    </div>
                  </div>
                  <button
                    onClick={() => toggleAddition(s.id)}
                    aria-label="Add student"
                    className="w-7 h-7 rounded-full bg-brand-light text-brand-primary flex items-center justify-center text-sm font-bold flex-shrink-0 hover:bg-brand-primary hover:text-white transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1"
                  >
                    +
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-4">
        <p className="text-sm text-brand-muted">
          {pendingRemovals.size > 0 || pendingAdditions.size > 0 ? (
            <span>
              {pendingAdditions.size > 0 && (
                <strong className="text-green-600 font-bold">
                  +{pendingAdditions.size} to add
                </strong>
              )}
              {pendingAdditions.size > 0 && pendingRemovals.size > 0 && " · "}
              {pendingRemovals.size > 0 && (
                <strong className="text-red-500 font-bold">
                  −{pendingRemovals.size} to remove
                </strong>
              )}
            </span>
          ) : (
            "No pending changes"
          )}
        </p>
        <div className="flex gap-2.5">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="border border-role-school-border rounded-full px-5 py-2.5 text-sm font-bold text-brand-body bg-white hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={
              isSaving ||
              (pendingRemovals.size === 0 && pendingAdditions.size === 0)
            }
            className="bg-brand-primary text-white rounded-full px-5 py-2.5 text-sm font-bold hover:bg-brand-primary/90 disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 transition-colors"
          >
            {isSaving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
