import { useState, useMemo } from "react";
import { Button, Input, Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
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

export function CreateClassModal({
  isOpen,
  onClose,
  onCreated,
}: CreateClassModalProps) {
  const [name, setName] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { data: curricula } = useCurricula();
  const { data: grades } = useGrades();
  const { data: subjects } = useSubjects();
  const { data: teachers } = useSchoolUsers(UserRole.TEACHER);
  const createClass = useCreateClass();

  const selectedGrade = useMemo(
    () => grades?.find((g) => g.id === gradeId),
    [grades, gradeId],
  );

  const curriculumId = useMemo(() => {
    if (!selectedGrade || !curricula) return "";
    if (selectedGrade.level <= 8) {
      return (
        curricula.find((c) => c.name.toLowerCase().includes("lower"))?.id ?? ""
      );
    }
    if (selectedGrade.level <= 10) {
      return (
        curricula.find((c) => c.name.toLowerCase().includes("igcse"))?.id ?? ""
      );
    }
    return "";
  }, [selectedGrade, curricula]);

  const academicYear = useMemo(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    return month >= 8 ? `${year}/${year + 1}` : `${year - 1}/${year}`;
  }, []);

  function resetForm() {
    setName("");
    setSubjectId("");
    setGradeId("");
    setTeacherId("");
    setErrors({});
  }

  const getSuggestedCurriculum = () => {
    if (!selectedGrade || !curricula) return "";
    if (selectedGrade.level <= 8) return "Cambridge Lower Secondary";
    if (selectedGrade.level <= 10) return "Cambridge IGCSE";
    return "Cambridge A-Level";
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) newErrors.name = "Class name is required";
    if (!subjectId) newErrors.subject = "Subject is required";
    if (!gradeId) newErrors.grade = "Grade is required";
    if (!curriculumId) newErrors.curriculum = "Curriculum is required";
    if (!teacherId) newErrors.teacher = "Teacher is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      await createClass.mutateAsync({
        name: name.trim(),
        subject_id: subjectId,
        grade_id: gradeId,
        curriculum_id: curriculumId,
        teacher_id: teacherId,
        academic_year: academicYear,
      });
      resetForm();
      onCreated();
      onClose();
    } catch {
      // Error handling done by caller
    }
  };

  function handleClose() {
    resetForm();
    onClose();
  }

  return (
    <Modal
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
      title="Create a new class"
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        <div>
          <Input
            id="className"
            label="Class name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Maths 9B"
            error={errors.name}
          />
        </div>

        <div>
          <label
            htmlFor="subject"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Subject <span className="text-brand-red">*</span>
          </label>
          <select
            id="subject"
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          >
            <option value="">Select subject</option>
            {subjects?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {errors.subject && (
            <p className="mt-1 text-xs text-brand-red">{errors.subject}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="grade"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Grade <span className="text-brand-red">*</span>
          </label>
          <select
            id="grade"
            value={gradeId}
            onChange={(e) => setGradeId(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          >
            <option value="">Select grade</option>
            {grades?.map((g) => (
              <option key={g.id} value={g.id}>
                Grade {g.level}
              </option>
            ))}
          </select>
          {errors.grade && (
            <p className="mt-1 text-xs text-brand-red">{errors.grade}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="curriculum"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Curriculum <span className="text-brand-red">*</span>
          </label>
          <select
            id="curriculum"
            value={curriculumId}
            disabled
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-gray-50 text-brand-ink font-sans text-sm cursor-not-allowed"
          >
            <option value="">Select curriculum</option>
            {curricula?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {errors.curriculum && (
            <p className="mt-1 text-xs text-brand-red">{errors.curriculum}</p>
          )}
          {gradeId && !errors.curriculum && (
            <p className="mt-1 text-xs text-brand-muted">
              Suggested: {getSuggestedCurriculum()}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="teacher"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Teacher <span className="text-brand-red">*</span>
          </label>
          <select
            id="teacher"
            value={teacherId}
            onChange={(e) => setTeacherId(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          >
            <option value="">Select teacher</option>
            {teachers?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name}
              </option>
            ))}
          </select>
          {errors.teacher && (
            <p className="mt-1 text-xs text-brand-red">{errors.teacher}</p>
          )}
        </div>

        <div className="flex gap-3 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={createClass.isPending}
            className="flex-1"
          >
            Create class →
          </Button>
        </div>
      </form>
    </Modal>
  );
}
