import { useState, useMemo } from "react";
import { Search, Plus, Minus } from "lucide-react";
import { Modal, Button } from "@kaihle/ui";
import {
  useClassStudents,
  useSchoolStudents,
  useEnrollStudents,
  useUnenrollStudents,
  type ClassStudent,
  type StudentListItem,
} from "../hooks/useSchoolAdmin";

interface ManageEnrollmentsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classId: string;
  className?: string;
  gradeLevel: number | null;
}

export function ManageEnrollmentsModal({
  open,
  onOpenChange,
  classId,
  className,
  gradeLevel,
}: ManageEnrollmentsModalProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [pendingRemovals, setPendingRemovals] = useState<Set<string>>(
    new Set(),
  );
  const [pendingAdditions, setPendingAdditions] = useState<Set<string>>(
    new Set(),
  );
  const [isSaving, setIsSaving] = useState(false);

  const { data: enrolledStudents, isLoading: enrolledLoading } =
    useClassStudents(classId);
  const { data: allStudents, isLoading: allStudentsLoading } =
    useSchoolStudents();
  const enrollStudents = useEnrollStudents(classId);
  const unenrollStudents = useUnenrollStudents(classId);

  // Filter out already enrolled students from available list
  const enrolledIds = useMemo(() => {
    const ids = new Set(enrolledStudents?.map((s) => s.id) ?? []);
    // Also exclude pending additions (they're already in the enrolled column visually)
    pendingAdditions.forEach((id) => ids.add(id));
    // Include pending removals back in available list
    pendingRemovals.forEach((id) => ids.delete(id));
    return ids;
  }, [enrolledStudents, pendingAdditions, pendingRemovals]);

  const availableStudents = useMemo(() => {
    if (!allStudents) return [];
    return allStudents.filter((s) => {
      if (gradeLevel !== null && s.grade_level !== gradeLevel) return false;
      return !enrolledIds.has(s.id);
    });
  }, [allStudents, enrolledIds, gradeLevel]);

  // Apply search filter
  const filteredAvailable = useMemo(() => {
    if (!searchQuery.trim()) return availableStudents;
    const q = searchQuery.toLowerCase();
    return availableStudents.filter(
      (s) =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        s.email.toLowerCase().includes(q),
    );
  }, [availableStudents, searchQuery]);

  const filteredEnrolled = useMemo(() => {
    if (!searchQuery.trim()) return enrolledStudents ?? [];
    const q = searchQuery.toLowerCase();
    return (enrolledStudents ?? []).filter(
      (s) =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        (s.email && s.email.toLowerCase().includes(q)),
    );
  }, [enrolledStudents, searchQuery]);

  const handleMarkForRemoval = (studentId: string) => {
    setPendingRemovals((prev) => {
      const next = new Set(prev);
      if (next.has(studentId)) {
        next.delete(studentId);
      } else {
        next.add(studentId);
      }
      return next;
    });
  };

  const handleMarkForAddition = (studentId: string) => {
    setPendingAdditions((prev) => {
      const next = new Set(prev);
      if (next.has(studentId)) {
        next.delete(studentId);
      } else {
        next.add(studentId);
      }
      return next;
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Process removals first
      if (pendingRemovals.size > 0) {
        await unenrollStudents.mutateAsync(Array.from(pendingRemovals));
      }

      // Process additions
      if (pendingAdditions.size > 0) {
        await enrollStudents.mutateAsync({
          student_ids: Array.from(pendingAdditions),
        });
      }

      // Reset and close
      setPendingRemovals(new Set());
      setPendingAdditions(new Set());
      setSearchQuery("");
      onOpenChange(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleClose = () => {
    setPendingRemovals(new Set());
    setPendingAdditions(new Set());
    setSearchQuery("");
    onOpenChange(false);
  };

  const hasChanges = pendingRemovals.size > 0 || pendingAdditions.size > 0;

  const enrolledCount =
    (enrolledStudents?.length ?? 0) -
    pendingRemovals.size +
    pendingAdditions.size;

  return (
    <Modal
      open={open}
      onOpenChange={handleClose}
      title={`Manage Enrollments${className ? ` — ${className}` : ""}`}
      description="Add or remove students from this class"
      maxWidth="2xl"
    >
      <div className="mt-4 space-y-4">
        {/* Search bar */}
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search students…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          />
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-2 gap-4 h-[400px]">
          {/* Enrolled column */}
          <div className="border border-role-school-border rounded-xl overflow-hidden flex flex-col">
            <div className="px-4 py-2 bg-gray-50 border-b border-role-school-border flex justify-between items-center">
              <span className="text-xs font-bold uppercase tracking-wider text-role-school-muted">
                Enrolled
              </span>
              <span className="text-xs text-brand-muted">{enrolledCount}</span>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {enrolledLoading ? (
                <div className="space-y-2 p-1">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-10 rounded-lg bg-gray-100 animate-pulse"
                    />
                  ))}
                </div>
              ) : (
                <>
                  {/* Current enrolled students (excluding pending removals) */}
                  {filteredEnrolled
                    .filter((s) => !pendingRemovals.has(s.id))
                    .map((student) => (
                      <StudentRow
                        key={student.id}
                        student={student}
                        action="remove"
                        onAction={() => handleMarkForRemoval(student.id)}
                      />
                    ))}
                  {/* Pending additions (shown in enrolled column) */}
                  {Array.from(pendingAdditions).map((studentId) => {
                    const student = allStudents?.find(
                      (s) => s.id === studentId,
                    );
                    if (!student) return null;
                    return (
                      <StudentRow
                        key={student.id}
                        student={student}
                        action="remove"
                        onAction={() => handleMarkForAddition(student.id)}
                        isPending
                      />
                    );
                  })}
                  {filteredEnrolled.length === 0 &&
                    pendingAdditions.size === 0 && (
                      <p className="text-center py-8 text-xs text-brand-muted">
                        No enrolled students
                      </p>
                    )}
                </>
              )}
            </div>
          </div>

          {/* Available column */}
          <div className="border border-role-school-border rounded-xl overflow-hidden flex flex-col">
            <div className="px-4 py-2 bg-gray-50 border-b border-role-school-border flex justify-between items-center">
              <span className="text-xs font-bold uppercase tracking-wider text-role-school-muted">
                Available
              </span>
              <span className="text-xs text-brand-muted">
                {filteredAvailable.length}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {allStudentsLoading ? (
                <div className="space-y-2 p-1">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-10 rounded-lg bg-gray-100 animate-pulse"
                    />
                  ))}
                </div>
              ) : (
                <>
                  {/* Available students (excluding pending additions) */}
                  {filteredAvailable
                    .filter((s) => !pendingAdditions.has(s.id))
                    .map((student) => (
                      <StudentRow
                        key={student.id}
                        student={student}
                        action="add"
                        onAction={() => handleMarkForAddition(student.id)}
                      />
                    ))}
                  {/* Pending removals (shown in available column) */}
                  {Array.from(pendingRemovals).map((studentId) => {
                    const student = enrolledStudents?.find(
                      (s) => s.id === studentId,
                    );
                    if (!student) return null;
                    return (
                      <StudentRow
                        key={student.id}
                        student={student}
                        action="add"
                        onAction={() => handleMarkForRemoval(student.id)}
                        isPending
                      />
                    );
                  })}
                  {filteredAvailable.length === 0 &&
                    pendingRemovals.size === 0 && (
                      <p className="text-center py-8 text-xs text-brand-muted">
                        No available students
                      </p>
                    )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Summary and actions */}
        <div className="flex items-center justify-between pt-2">
          <div className="text-sm">
            {hasChanges ? (
              <span className="text-brand-ink">
                <span className="font-semibold text-brand-green">
                  +{pendingAdditions.size}
                </span>{" "}
                to add,{" "}
                <span className="font-semibold text-brand-red">
                  -{pendingRemovals.size}
                </span>{" "}
                to remove
              </span>
            ) : (
              <span className="text-brand-muted">No changes</span>
            )}
          </div>
          <div className="flex gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={handleClose}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleSave}
              loading={isSaving}
              disabled={isSaving || !hasChanges}
            >
              Save changes
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

interface StudentRowProps {
  student: ClassStudent | StudentListItem;
  action: "add" | "remove";
  onAction: () => void;
  isPending?: boolean;
}

function StudentRow({ student, action, onAction, isPending }: StudentRowProps) {
  return (
    <div
      className={[
        "flex items-center justify-between px-3 py-2 rounded-lg text-sm",
        isPending
          ? action === "add"
            ? "bg-amber-50 border border-amber-200"
            : "bg-brand-green-light border border-brand-primary/30"
          : "bg-white border border-gray-100 hover:border-brand-border",
      ].join(" ")}
    >
      <div className="min-w-0">
        <p className="font-semibold text-brand-ink truncate">
          {student.first_name} {student.last_name}
        </p>
        <p className="text-xs text-brand-muted truncate">
          {(student as StudentListItem).username ??
            (student as ClassStudent).username ??
            (student as StudentListItem).email ??
            (student as ClassStudent).email}
        </p>
      </div>
      <button
        onClick={onAction}
        className={[
          "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ml-2 transition-colors",
          action === "add"
            ? "bg-brand-primary text-white hover:bg-brand-primary/90"
            : "bg-red-100 text-red-600 hover:bg-red-200",
        ].join(" ")}
        title={action === "add" ? "Add to class" : "Remove from class"}
      >
        {action === "add" ? (
          <Plus className="w-4 h-4" />
        ) : (
          <Minus className="w-4 h-4" />
        )}
      </button>
    </div>
  );
}
