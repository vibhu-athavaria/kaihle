import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Search, Info } from "lucide-react";
import { Button, Input, Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import { apiClient } from "@kaihle/auth";
import {
  useCurricula,
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

// ── Curriculum detection ──────────────────────────────────────────────────────

function detectCurriculumKeyword(gradeLevel: number): string {
  if (gradeLevel <= 5) return "primary";
  if (gradeLevel <= 8) return "lower";
  if (gradeLevel <= 10) return "igcse";
  return "a level";
}

function detectCurriculumLabel(gradeLevel: number): string {
  if (gradeLevel <= 5) return "Cambridge Primary";
  if (gradeLevel <= 8) return "Cambridge Lower Secondary";
  if (gradeLevel <= 10) return "Cambridge IGCSE";
  return "Cambridge AS & A Level";
}

function currentAcademicYear(): string {
  const year = new Date().getFullYear();
  const month = new Date().getMonth() + 1;
  return month >= 8 ? `${year}/${year + 1}` : `${year - 1}/${year}`;
}

// ── Label helper ──────────────────────────────────────────────────────────────

function FieldLabel({
  children,
  htmlFor,
  badge,
}: {
  children: React.ReactNode;
  htmlFor?: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <label
        htmlFor={htmlFor}
        className="block text-[11px] font-bold uppercase tracking-wider text-role-school-muted"
      >
        {children}
      </label>
      {badge}
    </div>
  );
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
  const [gradeId, setGradeId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [academicYear, setAcademicYear] = useState(currentAcademicYear);
  const [step1Errors, setStep1Errors] = useState<Record<string, string>>({});

  // Step 2 state
  const [teacherId, setTeacherId] = useState("");
  const [teacherSearch, setTeacherSearch] = useState("");

  // Step 3 state
  const [selectedStudentIds, setSelectedStudentIds] = useState<Set<string>>(
    new Set(),
  );
  const [studentSearch, setStudentSearch] = useState("");
  const [studentGradeFilter, setStudentGradeFilter] = useState<string>("all");

  const [submitting, setSubmitting] = useState(false);
  const [enrollError, setEnrollError] = useState("");
  const [createError, setCreateError] = useState("");

  const queryClient = useQueryClient();

  // Data hooks
  const { data: curricula } = useCurricula();
  const { data: grades } = useGrades();
  const selectedGrade = useMemo(
    () => grades?.find((g) => g.id === gradeId),
    [grades, gradeId],
  );
  const curriculumId = useMemo(() => {
    if (!selectedGrade || !curricula) return "";
    const keyword = detectCurriculumKeyword(selectedGrade.level);
    return (
      curricula.find((c) => c.name.toLowerCase().includes(keyword))?.id ?? ""
    );
  }, [selectedGrade, curricula]);

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

  // Students filtered by grade filter + search
  const gradeFilteredStudents = useMemo(() => {
    if (!students) return [];
    if (studentGradeFilter === "all") return students;
    return students.filter(() => {
      // Try to infer grade from student data if available
      // For now, we just return all since the API doesn't return grade per student
      // This will be refined when grade data is available on student objects
      return true;
    });
  }, [students, studentGradeFilter]);

  const filteredStudents = useMemo(() => {
    if (!gradeFilteredStudents) return [];
    const q = studentSearch.toLowerCase();
    if (!q) return gradeFilteredStudents;
    return gradeFilteredStudents.filter(
      (s) =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        s.email.toLowerCase().includes(q),
    );
  }, [gradeFilteredStudents, studentSearch]);

  const allStudentsSelected =
    filteredStudents.length > 0 &&
    filteredStudents.every((s) => selectedStudentIds.has(s.id));

  // Grade filter tabs (computed from students)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const gradeTabs = useMemo(() => {
    if (!students || !grades)
      return [] as Array<{ gradeId: string; level: number; count: number }>;
    // Since students don't have grade info from useSchoolUsers, we can't group them
    // Return empty for now — this feature needs backend support
    return [] as Array<{ gradeId: string; level: number; count: number }>;
  }, [students, grades]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const resetAll = useCallback(() => {
    setStep(1);
    setName("");
    setGradeId("");
    setSubjectId("");
    setAcademicYear(currentAcademicYear());
    setStep1Errors({});
    setTeacherId("");
    setTeacherSearch("");
    setSelectedStudentIds(new Set());
    setStudentSearch("");
    setStudentGradeFilter("all");
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
    setStep(3);
  }

  function handleStep2Skip() {
    setTeacherId("");
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
        teacher_id: teacherId || null,
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
    return (
      <div className="space-y-4">
        {/* Title + subtitle */}
        <div className="mb-2">
          <h2 className="font-display font-bold text-2xl text-brand-ink">
            Create New Class
          </h2>
          <p className="text-sm text-brand-body mt-1">
            Set up a class, assign a teacher, and add students
          </p>
        </div>

        <Input
          id="className"
          label="Class name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value.slice(0, 100))}
          placeholder="e.g. Grade 7 Mathematics"
          error={step1Errors.name}
        />
        <p className="text-xs text-brand-muted -mt-2">
          Give it a clear name teachers and students will recognise
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <FieldLabel htmlFor="grade">Grade</FieldLabel>
            <select
              id="grade"
              value={gradeId}
              onChange={(e) => {
                setGradeId(e.target.value);
                setSubjectId(""); // reset subject when grade changes
              }}
              className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            >
              <option value="">Select grade</option>
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
            <FieldLabel
              badge={
                <span className="text-[10px] font-bold uppercase tracking-wider text-brand-primary bg-brand-green-light px-2 py-0.5 rounded-full">
                  Auto-detected
                </span>
              }
            >
              Curriculum
            </FieldLabel>
            <div className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-gray-50 text-brand-muted font-sans text-sm">
              {gradeId && selectedGrade
                ? detectCurriculumLabel(selectedGrade.level)
                : "—"}
            </div>
          </div>
        </div>

        <div>
          <FieldLabel>Subject</FieldLabel>
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
          <p className="text-xs text-brand-muted mt-1">
            Pulled from your school&apos;s active subjects
          </p>
        </div>

        <div>
          <FieldLabel
            htmlFor="academicYear"
            badge={
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-primary bg-brand-green-light px-2 py-0.5 rounded-full">
                Auto-filled
              </span>
            }
          >
            Academic Year
          </FieldLabel>
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
            Next: Assign Teacher →
          </Button>
        </div>
      </div>
    );
  }

  function renderStep2() {
    return (
      <div className="space-y-4">
        <p className="text-[11px] font-bold text-role-school-muted uppercase tracking-wider">
          Select a Teacher{" "}
          <span className="text-[10px] font-medium normal-case tracking-normal text-gray-400">
            (optional — can be assigned later)
          </span>
        </p>
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search teachers by name..."
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

        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setStep(1)}
            className="flex-shrink-0"
          >
            ← Back
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={handleStep2Skip}
            className="flex-1"
          >
            Skip for now
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleStep2Next}
            className="flex-1"
          >
            Next: Add Students →
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

        <p className="text-[11px] font-bold text-role-school-muted uppercase tracking-wider">
          Select Students{" "}
          <span className="text-[10px] font-medium normal-case tracking-normal text-gray-400">
            (optional — can enrol later)
          </span>
        </p>

        {/* Grade filter tabs */}
        {gradeTabs.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setStudentGradeFilter("all")}
              className={[
                "px-3 py-1.5 rounded-full text-xs font-semibold font-sans transition-all",
                studentGradeFilter === "all"
                  ? "bg-brand-primary text-white"
                  : "border border-role-school-border text-brand-body hover:border-brand-primary hover:text-brand-primary",
              ].join(" ")}
            >
              All Grades
            </button>
            {gradeTabs.map((tab) => (
              <button
                key={tab.gradeId}
                type="button"
                onClick={() => setStudentGradeFilter(tab.gradeId)}
                className={[
                  "px-3 py-1.5 rounded-full text-xs font-semibold font-sans transition-all",
                  studentGradeFilter === tab.gradeId
                    ? "bg-brand-primary text-white"
                    : "border border-role-school-border text-brand-body hover:border-brand-primary hover:text-brand-primary",
                ].join(" ")}
              >
                Grade {tab.level} ({tab.count})
              </button>
            ))}
          </div>
        )}

        {/* Search */}
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search students by name..."
            value={studentSearch}
            onChange={(e) => setStudentSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          />
        </div>

        {/* Select all + count */}
        {filteredStudents.length > 0 && (
          <div className="flex items-center justify-between">
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
                Select all{" "}
                {studentGradeFilter !== "all" && gradeTabs.length > 0
                  ? `Grade ${gradeTabs.find((g) => g.gradeId === studentGradeFilter)?.level ?? ""} students`
                  : "students"}
              </span>
            </label>
            <span className="text-sm font-semibold text-brand-primary">
              {selectedList.length} selected
            </span>
          </div>
        )}

        {/* Table header */}
        {filteredStudents.length > 0 && (
          <div className="grid grid-cols-[auto_1fr_1fr_1fr] gap-3 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-brand-muted border-b border-brand-border">
            <div className="w-4" />
            <span>Student</span>
            <span>Grade</span>
            <span>Status</span>
          </div>
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
                  "grid grid-cols-[auto_1fr_1fr_1fr] gap-3 items-center px-4 py-3 rounded-xl border cursor-pointer transition-all",
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
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-brand-ink truncate">
                    {s.first_name} {s.last_name}
                  </p>
                  <p className="text-xs text-brand-muted truncate">{s.email}</p>
                </div>
                <span className="text-sm text-brand-body">—</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-brand-green-light text-brand-primary w-fit">
                  Active
                </span>
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
            ✓ Create Class{" "}
            {selectedList.length > 0 ? `(${selectedList.length} students)` : ""}
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
