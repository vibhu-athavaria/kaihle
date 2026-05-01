import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Search, Info } from "lucide-react";
import { Button, Input, Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import { apiClient } from "@kaihle/auth";
import {
  useMySchoolCurricula,
  useGrades,
  useSubjects,
  useSchoolUsers,
  useCreateClass,
} from "../hooks/useSchoolAdmin";

interface CreateClassModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

// ── Step Progress Bar ─────────────────────────────────────────────────────────

interface StepBarProps {
  current: 1 | 2 | 3;
}

function StepBar({ current }: StepBarProps) {
  const steps = [
    { n: 1, label: "Class Details" },
    { n: 2, label: "Assign Teacher" },
    { n: 3, label: "Add Students" },
  ];

  return (
    <div
      className="flex items-center mb-6"
      role="list"
      aria-label="Form progress"
    >
      {steps.map((step, idx) => {
        const done = step.n < current;
        const active = step.n === current;
        const state = done ? "done" : active ? "active" : "upcoming";

        return (
          <div key={step.n} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center">
              <div
                role="listitem"
                aria-label={`Step ${step.n}: ${step.label}${state === "done" ? " (completed)" : state === "active" ? " (current)" : ""}`}
                aria-current={state === "active" ? "step" : undefined}
                className={[
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all",
                  done
                    ? "bg-brand-primary text-white"
                    : active
                      ? "bg-brand-primary text-white ring-4 ring-brand-primary/20"
                      : "bg-gray-100 text-gray-400",
                ].join(" ")}
              >
                {done ? (
                  <Check className="w-4 h-4" aria-hidden="true" />
                ) : (
                  step.n
                )}
              </div>
              <span
                className={[
                  "text-[10px] font-sans mt-1 whitespace-nowrap",
                  active ? "text-brand-primary font-semibold" : "text-gray-400",
                ].join(" ")}
              >
                {step.label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div
                className={[
                  "flex-1 h-0.5 mx-2 mb-4 rounded transition-all",
                  done ? "bg-brand-primary" : "bg-gray-200",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function currentAcademicYear(): string {
  const year = new Date().getFullYear();
  const month = new Date().getMonth() + 1;
  return month >= 8 ? `${year}/${year + 1}` : `${year - 1}/${year}`;
}

// ── Main component ────────────────────────────────────────────────────────────

export function CreateClassModal({
  isOpen,
  onClose,
  onCreated,
}: CreateClassModalProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1 state
  const [name, setName] = useState("");
  const [curriculumId, setCurriculumId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [academicYear, setAcademicYear] = useState(currentAcademicYear);
  const [step1Errors, setStep1Errors] = useState<Record<string, string>>({});

  // Step 2 state
  const [teacherId, setTeacherId] = useState("");
  const [teacherSearch, setTeacherSearch] = useState("");
  const [step2Error, setStep2Error] = useState("");

  // Step 3 state
  const [selectedStudentIds, setSelectedStudentIds] = useState<Set<string>>(
    new Set(),
  );
  const [studentSearch, setStudentSearch] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [enrollError, setEnrollError] = useState("");
  const [createError, setCreateError] = useState("");

  const queryClient = useQueryClient();

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
  const { data: students, isLoading: studentsLoading } = useSchoolUsers(
    UserRole.STUDENT,
  );

  const createClass = useCreateClass();

  // ── Derived lists ───────────────────────────────────────────────────────────

  const filteredTeachers = useMemo(() => {
    if (!teachers) return [];
    const q = teacherSearch.toLowerCase();
    if (!q) return teachers;
    return teachers.filter(
      (t) =>
        `${t.first_name} ${t.last_name}`.toLowerCase().includes(q) ||
        t.email.toLowerCase().includes(q),
    );
  }, [teachers, teacherSearch]);

  const filteredStudents = useMemo(() => {
    if (!students) return [];
    const q = studentSearch.toLowerCase();
    if (!q) return students;
    return students.filter(
      (s) =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        s.email.toLowerCase().includes(q),
    );
  }, [students, studentSearch]);

  const allStudentsSelected =
    filteredStudents.length > 0 &&
    filteredStudents.every((s) => selectedStudentIds.has(s.id));

  // ── Handlers ────────────────────────────────────────────────────────────────

  const resetAll = useCallback(() => {
    setStep(1);
    setName("");
    setCurriculumId("");
    setGradeId("");
    setSubjectId("");
    setAcademicYear(currentAcademicYear());
    setStep1Errors({});
    setTeacherId("");
    setTeacherSearch("");
    setStep2Error("");
    setSelectedStudentIds(new Set());
    setStudentSearch("");
    setSubmitting(false);
    setEnrollError("");
    setCreateError("");
  }, []);

  function handleClose() {
    resetAll();
    onClose();
  }

  const ACADEMIC_YEAR_REGEX = /^\d{4}\/\d{4}$/;

  function validateStep1(): boolean {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Class name is required";
    if (!curriculumId) errs.curriculum = "Curriculum is required";
    if (!subjectId) errs.subject = "Subject is required";
    if (!gradeId) errs.grade = "Grade is required";
    if (!ACADEMIC_YEAR_REGEX.test(academicYear)) {
      errs.academicYear =
        "Academic year must be in format YYYY/YYYY (e.g. 2025/2026)";
    }
    setStep1Errors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleStep1Next() {
    if (validateStep1()) setStep(2);
  }

  function handleStep2Next() {
    if (!teacherId) {
      setStep2Error("Please assign a teacher to this class");
      return;
    }
    setStep(3);
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
    if (allStudentsSelected) {
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

  async function handleSubmit(studentIds: string[]) {
    if (!curriculumId || submitting) return;
    setCreateError("");
    setSubmitting(true);
    try {
      const created = await createClass.mutateAsync({
        name: name.trim(),
        subject_id: subjectId,
        grade_id: gradeId,
        curriculum_id: curriculumId,
        teacher_id: teacherId,
        academic_year: academicYear,
      });

      const newClassId = created.id;

      if (studentIds.length > 0) {
        try {
          await apiClient.post(`/api/v1/classes/${newClassId}/enrollments`, {
            student_ids: studentIds,
          });
          queryClient.invalidateQueries({ queryKey: ["school", "classes"] });
        } catch {
          setEnrollError(
            "Class created, but some students couldn't be enrolled. You can enrol them from the class page.",
          );
          setSubmitting(false);
          return;
        }
      }

      resetAll();
      onCreated();
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message.includes("409")
          ? "A class with this name already exists for this school year."
          : "Something went wrong. Please try again.";
      setCreateError(message);
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render helpers ──────────────────────────────────────────────────────────

  function renderStep1() {
    const noCurricula =
      !curriculaLoading &&
      subscribedCurricula !== undefined &&
      subscribedCurricula.length === 0;

    if (noCurricula) {
      return (
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
      );
    }

    return (
      <div className="space-y-4">
        <Input
          id="className"
          label="Class name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value.slice(0, 100))}
          placeholder="e.g. Maths 9B"
          error={step1Errors.name}
        />

        <div>
          <label className="block text-sm font-semibold text-brand-ink mb-1.5">
            Curriculum <span className="text-brand-red">*</span>
          </label>
          <select
            value={curriculumId}
            onChange={(e) => {
              setCurriculumId(e.target.value);
              setGradeId("");
              setSubjectId("");
            }}
            disabled={curriculaLoading}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary disabled:opacity-60"
          >
            <option value="">
              {curriculaLoading ? "Loading…" : "Select curriculum"}
            </option>
            {subscribedCurricula?.map((c) => (
              <option key={c.curriculum_id} value={c.curriculum_id}>
                {c.curriculum_name}
              </option>
            ))}
          </select>
          {step1Errors.curriculum && (
            <p className="mt-1 text-xs text-brand-red">
              {step1Errors.curriculum}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-semibold text-brand-ink mb-1.5">
            Grade <span className="text-brand-red">*</span>
          </label>
          <select
            value={gradeId}
            onChange={(e) => {
              setGradeId(e.target.value);
              setSubjectId("");
            }}
            disabled={!curriculumId || gradesLoading}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary disabled:opacity-60"
          >
            <option value="">
              {!curriculumId
                ? "Select curriculum first"
                : gradesLoading
                  ? "Loading grades…"
                  : "Select grade"}
            </option>
            {grades?.map((g) => (
              <option key={g.id} value={g.id}>
                Grade {g.level}
              </option>
            ))}
          </select>
          {step1Errors.grade && (
            <p className="mt-1 text-xs text-brand-red">{step1Errors.grade}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-semibold text-brand-ink mb-2">
            Subject <span className="text-brand-red">*</span>
          </label>
          <div className="flex flex-wrap gap-2">
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
                  ? "No subjects available for this curriculum. Contact support if this is unexpected."
                  : "Select a grade first"}
              </span>
            )}
          </div>
          {step1Errors.subject && (
            <p className="mt-1 text-xs text-brand-red">{step1Errors.subject}</p>
          )}
        </div>

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
            aria-invalid={!!step1Errors.academicYear}
            aria-describedby={
              step1Errors.academicYear ? "academicYear-error" : undefined
            }
            pattern="^\d{4}/\d{4}$"
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          />
          {step1Errors.academicYear && (
            <p id="academicYear-error" className="mt-1 text-xs text-brand-red">
              {step1Errors.academicYear}
            </p>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleStep1Next}
            className="flex-1"
          >
            Next →
          </Button>
        </div>
      </div>
    );
  }

  function renderStep2() {
    return (
      <div className="space-y-4">
        <p className="text-[11px] font-bold text-role-school-muted uppercase tracking-wider mb-4">
          Select a Teacher <span className="text-brand-red">*</span>
        </p>
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search teachers..."
            value={teacherSearch}
            onChange={(e) => setTeacherSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          />
        </div>

        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {teachersLoading && (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-16 rounded-xl bg-gray-100 animate-pulse"
                />
              ))}
            </div>
          )}

          {!teachersLoading && filteredTeachers.length === 0 && (
            <div className="text-center py-10 text-sm text-brand-muted">
              {teachers?.length === 0
                ? "No teachers in this school yet."
                : "No teachers match your search."}
            </div>
          )}

          {filteredTeachers.map((t) => {
            const selected = teacherId === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setTeacherId(selected ? "" : t.id);
                  setStep2Error("");
                }}
                className={[
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-all",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
                  selected
                    ? "bg-brand-green-light border-brand-primary"
                    : "border-role-school-border hover:border-brand-primary/50",
                ].join(" ")}
              >
                <div className="w-9 h-9 rounded-full bg-brand-primary/10 flex items-center justify-center text-brand-primary font-bold text-sm flex-shrink-0">
                  {t.first_name?.[0]}
                  {t.last_name?.[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm text-brand-ink truncate">
                    {t.first_name} {t.last_name}
                  </p>
                  <p className="text-xs text-brand-muted truncate">{t.email}</p>
                </div>
                {selected && (
                  <Check
                    className="w-4 h-4 text-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                )}
              </button>
            );
          })}
        </div>

        {step2Error && (
          <p className="mt-2 text-xs text-brand-red">{step2Error}</p>
        )}

        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setStep(1)}
            className="flex-1"
          >
            ← Back
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleStep2Next}
            disabled={!teacherId}
            className="flex-1"
          >
            Next →
          </Button>
        </div>
      </div>
    );
  }

  const selectAllRef = useRef<HTMLInputElement>(null);
  const someSelected =
    filteredStudents.some((s) => selectedStudentIds.has(s.id)) &&
    !allStudentsSelected;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  function renderStep3() {
    const selectedList = Array.from(selectedStudentIds);

    return (
      <div className="space-y-4">
        {/* Info banner */}
        <div className="flex gap-3 items-start bg-brand-green-light border border-role-school-border rounded-xl p-3.5 mb-4 text-sm text-brand-ink">
          <Info
            className="w-4 h-4 text-brand-primary mt-0.5 flex-shrink-0"
            aria-hidden="true"
          />
          <p className="text-xs font-sans leading-relaxed">
            A Tier 1 Diagnostic will be automatically generated for each student
            enrolled.
          </p>
        </div>

        <p className="text-[11px] font-bold text-role-school-muted uppercase tracking-wider mb-4">
          Select Students{" "}
          <span className="text-[10px] font-medium normal-case tracking-normal text-gray-400">
            (optional — can enrol later)
          </span>
        </p>

        {/* Search */}
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search students..."
            value={studentSearch}
            onChange={(e) => setStudentSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          />
        </div>

        {/* Select all */}
        {filteredStudents.length > 0 && (
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              ref={selectAllRef}
              type="checkbox"
              checked={allStudentsSelected}
              onChange={toggleSelectAll}
              aria-label={`Select all ${filteredStudents.length} students`}
              className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-primary"
            />
            <span className="text-sm font-semibold text-brand-ink">
              Select all ({filteredStudents.length})
            </span>
          </label>
        )}

        {/* Student list */}
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          {studentsLoading && (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-14 rounded-xl bg-gray-100 animate-pulse"
                />
              ))}
            </div>
          )}

          {!studentsLoading && filteredStudents.length === 0 && (
            <div className="text-center py-8 text-sm text-brand-muted">
              {students?.length === 0
                ? "No students in this school yet."
                : "No students match your search."}
            </div>
          )}

          {filteredStudents.map((s) => {
            const checked = selectedStudentIds.has(s.id);
            return (
              <label
                key={s.id}
                className={[
                  "flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all",
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
                  <p className="text-xs text-brand-muted truncate">{s.email}</p>
                </div>
              </label>
            );
          })}
        </div>

        {createError && (
          <div className="text-xs text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">
            {createError}
          </div>
        )}

        {enrollError && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
            {enrollError}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setStep(2)}
            className="flex-shrink-0"
          >
            ← Back
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => handleSubmit([])}
            loading={submitting && selectedList.length === 0}
            disabled={submitting}
            className="flex-1 border border-gray-200 text-gray-500 rounded-full"
          >
            Create without students
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={() => handleSubmit(selectedList)}
            loading={submitting && selectedList.length > 0}
            disabled={submitting}
            className="flex-1"
          >
            ✓ Create Class
            {selectedList.length > 0 ? ` (${selectedList.length})` : ""}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Modal
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
      title="Create a New Class"
      maxWidth="lg"
    >
      <div className="mt-4">
        <StepBar current={step} />
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
      </div>
    </Modal>
  );
}
