import { useState, useMemo } from "react";
import { Button, Input, Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import {
  useCurricula,
  useGrades,
  useSchoolUsers,
  useCreateClass,
} from "../hooks/useSchoolAdmin";

interface CreateClassModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const subjectOptions = [
  { value: "MATH", label: "Mathematics" },
  { value: "SCI", label: "Science" },
  { value: "ENG", label: "English" },
  { value: "BIO", label: "Biology" },
  { value: "CHEM", label: "Chemistry" },
  { value: "PHY", label: "Physics" },
  { value: "ENGL", label: "English Literature" },
];

export function CreateClassModal({
  isOpen,
  onClose,
  onCreated,
}: CreateClassModalProps) {
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { data: curricula } = useCurricula();
  const { data: grades } = useGrades();
  const { data: teachers } = useSchoolUsers(UserRole.TEACHER);
  const createClass = useCreateClass();

  const curriculumId = useMemo(() => {
    if (!grade || !curricula || !grades) return "";
    const gradeData = grades.find((g) => g.level === parseInt(grade));
    if (!gradeData) return "";
    if (gradeData.level <= 8) {
      return (
        curricula.find((c) => c.name.toLowerCase().includes("lower"))?.id ?? ""
      );
    }
    if (gradeData.level <= 10) {
      return (
        curricula.find((c) => c.name.toLowerCase().includes("igcse"))?.id ?? ""
      );
    }
    return "";
  }, [grade, curricula, grades]);

  function resetForm() {
    setName("");
    setSubject("");
    setGrade("");
    setTeacherId("");
    setErrors({});
  }

  const getSuggestedCurriculum = () => {
    if (!grade || !curricula) return "";
    const gradeNum = parseInt(grade);
    if (gradeNum <= 8) {
      return "Cambridge Lower Secondary";
    }
    if (gradeNum <= 10) {
      return "Cambridge IGCSE";
    }
    return "Cambridge A-Level";
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) {
      newErrors.name = "Class name is required";
    }
    if (!subject) {
      newErrors.subject = "Subject is required";
    }
    if (!grade) {
      newErrors.grade = "Grade is required";
    }
    if (!curriculumId) {
      newErrors.curriculum = "Curriculum is required";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      await createClass.mutateAsync({
        name: name.trim(),
        subject,
        grade: parseInt(grade),
        curriculum_id: curriculumId,
        teacher_id: teacherId || undefined,
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
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          >
            <option value="">Select subject</option>
            {subjectOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
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
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          >
            <option value="">Select grade</option>
            {grades?.map((g) => (
              <option key={g.id} value={g.level}>
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
          {grade && !errors.curriculum && (
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
            Teacher (optional)
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
