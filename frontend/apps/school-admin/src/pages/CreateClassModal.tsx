import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { Search } from "lucide-react";
import { Button, Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import {
  useMySchoolCurricula,
  useGrades,
  useSubjects,
  useSchoolUsers,
  useCreateClass,
  type User,
} from "../hooks/useSchoolAdmin";

interface CreateClassModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

function currentAcademicYear(): string {
  const year = new Date().getFullYear();
  const month = new Date().getMonth() + 1;
  return month >= 8 ? `${year}/${year + 1}` : `${year - 1}/${year}`;
}

const ACADEMIC_YEAR_REGEX = /^\d{4}\/\d{4}$/;

function SelectField({
  id,
  label,
  value,
  onChange,
  disabled,
  children,
  error,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
  error?: string;
  hint?: string;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-semibold text-brand-ink mb-1.5"
      >
        {label}
        {hint && (
          <span className="ml-2 text-[10px] font-medium normal-case tracking-normal text-brand-primary bg-brand-green-light px-1.5 py-0.5 rounded-full">
            {hint}
          </span>
        )}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary disabled:opacity-60"
      >
        {children}
      </select>
      {error && <p className="mt-1 text-xs text-brand-red">{error}</p>}
    </div>
  );
}

export function CreateClassModal({
  isOpen,
  onClose,
  onCreated,
}: CreateClassModalProps) {
  // Form fields
  const [name, setName] = useState("");
  const [curriculumId, setCurriculumId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [academicYear, setAcademicYear] = useState(currentAcademicYear);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Student picker
  const [selectedStudentIds, setSelectedStudentIds] = useState<Set<string>>(
    new Set(),
  );
  const [studentSearch, setStudentSearch] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // Data hooks
  const { data: subscribedCurricula, isLoading: curriculaLoading } =
    useMySchoolCurricula();
  const { data: grades, isLoading: gradesLoading } = useGrades(
    curriculumId || undefined,
  );
  const { data: allSubjects } = useSubjects(curriculumId || undefined);
  const { data: teachers, isLoading: teachersLoading } = useSchoolUsers(
    UserRole.TEACHER,
  );
  const { data: allStudents, isLoading: studentsLoading } = useSchoolUsers(
    UserRole.STUDENT,
  );

  const createClass = useCreateClass();

  // ── Derived grade level (to filter students) ────────────────────────────────

  const selectedGradeLevel = useMemo(() => {
    if (!gradeId || !grades) return null;
    return grades.find((g) => g.id === gradeId)?.level ?? null;
  }, [gradeId, grades]);

  // Students matching the selected grade, with "in another class" detection
  // We use class_count as a proxy — students already in at least one class get the badge.
  const gradeStudents = useMemo<User[]>(() => {
    if (!allStudents) return [];
    if (selectedGradeLevel === null) return [];
    return allStudents.filter((s) => s.grade_level === selectedGradeLevel);
  }, [allStudents, selectedGradeLevel]);

  const filteredStudents = useMemo(() => {
    const q = studentSearch.toLowerCase();
    if (!q) return gradeStudents;
    return gradeStudents.filter(
      (s) =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        s.email.toLowerCase().includes(q),
    );
  }, [gradeStudents, studentSearch]);

  const allSelected =
    filteredStudents.length > 0 &&
    filteredStudents.every((s) => selectedStudentIds.has(s.id));
  const someSelected =
    filteredStudents.some((s) => selectedStudentIds.has(s.id)) && !allSelected;

  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const reset = useCallback(() => {
    setName("");
    setCurriculumId("");
    setGradeId("");
    setSubjectId("");
    setTeacherId("");
    setAcademicYear(currentAcademicYear());
    setErrors({});
    setSelectedStudentIds(new Set());
    setStudentSearch("");
    setSubmitting(false);
    setSubmitError("");
  }, []);

  function handleClose() {
    reset();
    onClose();
  }

  function toggleStudent(id: string) {
    setSelectedStudentIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedStudentIds((prev) => {
        const next = new Set(prev);
        filteredStudents.forEach((s) => next.delete(s.id));
        return next;
      });
    } else {
      setSelectedStudentIds((prev) => {
        const next = new Set(prev);
        filteredStudents.forEach((s) => next.add(s.id));
        return next;
      });
    }
  }

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Class name is required";
    if (!gradeId) errs.grade = "Grade is required";
    if (!curriculumId) errs.curriculum = "Curriculum is required";
    if (!subjectId) errs.subject = "Subject is required";
    if (!teacherId) errs.teacher = "Teacher is required";
    if (!ACADEMIC_YEAR_REGEX.test(academicYear))
      errs.academicYear = "Format: YYYY/YYYY";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate() || submitting) return;
    setSubmitError("");
    setSubmitting(true);
    try {
      await createClass.mutateAsync({
        name: name.trim(),
        subject_id: subjectId,
        grade_id: gradeId,
        curriculum_id: curriculumId,
        teacher_id: teacherId,
        academic_year: academicYear,
        student_ids:
          selectedStudentIds.size > 0
            ? Array.from(selectedStudentIds)
            : undefined,
      });
      reset();
      onCreated();
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message.includes("409")
          ? "A class with this name already exists for this school year."
          : "Something went wrong. Please try again.";
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const noCurricula =
    !curriculaLoading &&
    subscribedCurricula !== undefined &&
    subscribedCurricula.length === 0;

  return (
    <Modal
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
      title="Create a New Class"
      maxWidth="lg"
    >
      {noCurricula ? (
        <div className="py-8 text-center space-y-3">
          <p className="text-sm font-semibold text-brand-ink">
            No curricula assigned to this school yet.
          </p>
          <p className="text-xs text-brand-body">
            Contact your Kaihle administrator to assign a curriculum before
            creating classes.
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            className="mt-4"
          >
            Close
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-5">
          {/* Row 1: Class name + Grade */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="className"
                className="block text-sm font-semibold text-brand-ink mb-1.5"
              >
                Class name <span className="text-brand-red">*</span>
              </label>
              <input
                id="className"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value.slice(0, 100))}
                placeholder="e.g. Maths 9B"
                className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
              />
              {errors.name && (
                <p className="mt-1 text-xs text-brand-red">{errors.name}</p>
              )}
            </div>

            <SelectField
              id="grade"
              label="Grade *"
              value={gradeId}
              onChange={(v) => {
                setGradeId(v);
                setSubjectId("");
                setSelectedStudentIds(new Set());
              }}
              disabled={!curriculumId || gradesLoading}
              error={errors.grade}
              hint={gradeId ? "loads students below" : undefined}
            >
              <option value="">
                {!curriculumId
                  ? "Select curriculum first"
                  : gradesLoading
                    ? "Loading…"
                    : "Select grade"}
              </option>
              {grades?.map((g) => (
                <option key={g.id} value={g.id}>
                  Grade {g.level}
                </option>
              ))}
            </SelectField>
          </div>

          {/* Row 2: Curriculum + Subject */}
          <div className="grid grid-cols-2 gap-4">
            <SelectField
              id="curriculum"
              label="Curriculum *"
              value={curriculumId}
              onChange={(v) => {
                setCurriculumId(v);
                setGradeId("");
                setSubjectId("");
                setSelectedStudentIds(new Set());
              }}
              disabled={curriculaLoading}
              error={errors.curriculum}
            >
              <option value="">
                {curriculaLoading ? "Loading…" : "Select curriculum"}
              </option>
              {subscribedCurricula?.map((c) => (
                <option key={c.curriculum_id} value={c.curriculum_id}>
                  {c.curriculum_name}
                </option>
              ))}
            </SelectField>

            <div>
              <label className="block text-sm font-semibold text-brand-ink mb-1.5">
                Subject <span className="text-brand-red">*</span>
              </label>
              <div className="flex flex-wrap gap-2 min-h-[42px] items-center">
                {allSubjects?.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSubjectId(s.id)}
                    className={[
                      "px-3 py-1.5 rounded-full text-xs font-semibold font-sans transition-all",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
                      subjectId === s.id
                        ? "bg-brand-primary text-white"
                        : "border border-role-school-border text-brand-body hover:border-brand-primary hover:text-brand-primary",
                    ].join(" ")}
                  >
                    {s.name}
                  </button>
                ))}
                {!allSubjects?.length && (
                  <span className="text-sm text-brand-muted">
                    {gradeId
                      ? "No subjects for this curriculum"
                      : "Select grade first"}
                  </span>
                )}
              </div>
              {errors.subject && (
                <p className="mt-1 text-xs text-brand-red">{errors.subject}</p>
              )}
            </div>
          </div>

          {/* Row 3: Teacher + Academic Year */}
          <div className="grid grid-cols-2 gap-4">
            <SelectField
              id="teacher"
              label="Teacher *"
              value={teacherId}
              onChange={setTeacherId}
              disabled={teachersLoading}
              error={errors.teacher}
            >
              <option value="">
                {teachersLoading ? "Loading…" : "Select teacher"}
              </option>
              {teachers?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.first_name} {t.last_name}
                </option>
              ))}
            </SelectField>

            <div>
              <label
                htmlFor="academicYear"
                className="block text-sm font-semibold text-brand-ink mb-1.5"
              >
                Academic Year
              </label>
              <input
                id="academicYear"
                type="text"
                value={academicYear}
                onChange={(e) => setAcademicYear(e.target.value)}
                pattern="^\d{4}/\d{4}$"
                className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
              />
              {errors.academicYear && (
                <p className="mt-1 text-xs text-brand-red">
                  {errors.academicYear}
                </p>
              )}
            </div>
          </div>

          {/* Student picker — only shown once a grade is selected */}
          {gradeId && (
            <div className="border border-role-school-border rounded-xl overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-role-school-border">
                <p className="text-xs font-bold text-role-school-muted uppercase tracking-wider">
                  {selectedGradeLevel !== null
                    ? `Grade ${selectedGradeLevel} Students`
                    : "Students"}
                  {gradeStudents.length > 0 && (
                    <span className="ml-2 font-medium normal-case tracking-normal text-gray-400">
                      — {gradeStudents.length} available
                    </span>
                  )}
                </p>
                {selectedStudentIds.size > 0 && (
                  <span className="text-xs font-semibold text-brand-primary">
                    {selectedStudentIds.size} selected
                  </span>
                )}
              </div>

              <div className="p-3 space-y-3">
                {/* Search */}
                <div className="relative">
                  <Search
                    className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                    aria-hidden="true"
                  />
                  <input
                    type="text"
                    placeholder="Search students…"
                    value={studentSearch}
                    onChange={(e) => setStudentSearch(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 rounded-lg border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                  />
                </div>

                {/* Select all */}
                {filteredStudents.length > 0 && (
                  <label className="flex items-center gap-2 cursor-pointer select-none px-1">
                    <input
                      ref={selectAllRef}
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      aria-label={`Select all ${filteredStudents.length} students`}
                      className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-primary"
                    />
                    <span className="text-xs font-semibold text-brand-ink">
                      Select all ({filteredStudents.length})
                    </span>
                  </label>
                )}

                {/* Student list */}
                <div className="space-y-1.5 max-h-52 overflow-y-auto">
                  {studentsLoading && (
                    <div className="space-y-2 p-1">
                      {[1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className="h-10 rounded-lg bg-gray-100 animate-pulse"
                        />
                      ))}
                    </div>
                  )}

                  {!studentsLoading && gradeStudents.length === 0 && (
                    <p className="text-center py-6 text-xs text-brand-muted">
                      No students at this grade level yet.
                    </p>
                  )}

                  {!studentsLoading &&
                    gradeStudents.length > 0 &&
                    filteredStudents.length === 0 && (
                      <p className="text-center py-4 text-xs text-brand-muted">
                        No students match your search.
                      </p>
                    )}

                  {filteredStudents.map((s) => {
                    const checked = selectedStudentIds.has(s.id);
                    // Use class_count from StudentListItem if available — proxy for "already in a class"
                    // The User type from useSchoolUsers doesn't carry class_count; we fall back to
                    // checking via allStudents cast where we can access the richer StudentListItem shape.
                    const inAnotherClass = false; // placeholder — enriched in future task

                    return (
                      <label
                        key={s.id}
                        className={[
                          "flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-all",
                          checked
                            ? "bg-brand-green-light border-brand-primary"
                            : "border-role-school-border hover:border-brand-primary/50",
                        ].join(" ")}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleStudent(s.id)}
                          className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-primary"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-sm text-brand-ink truncate">
                            {s.first_name} {s.last_name}
                          </p>
                          <p className="text-xs text-brand-muted truncate">
                            {s.email}
                          </p>
                        </div>
                        {inAnotherClass && (
                          <span className="flex-shrink-0 text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
                            In another class
                          </span>
                        )}
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {submitError && (
            <div className="text-xs text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {submitError}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <Button
              type="button"
              variant="secondary"
              onClick={handleClose}
              disabled={submitting}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={submitting}
              disabled={submitting}
              className="flex-1"
            >
              {selectedStudentIds.size > 0
                ? `Create Class (${selectedStudentIds.size} students)`
                : "Create Class"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
