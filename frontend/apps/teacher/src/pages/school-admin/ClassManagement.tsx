import { useState } from "react";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { Badge } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { Plus, X, BookOpen } from "lucide-react";
import {
  useSchoolClasses,
  useSchoolUsers,
  useUpdateClass,
  useEnrollStudents,
  type Class,
  type User as UserType,
} from "../../hooks/useSchoolAdmin";
import { CreateClassModal } from "./CreateClassModal";

function getInitials(firstName: string, lastName: string): string {
  const first = firstName?.[0] || "";
  const last = lastName?.[0] || "";
  return (first + last).toUpperCase() || "?";
}

function ClassDetailPanel({
  cls,
  teachers,
  students,
  onClose,
  onUpdateTeacher,
  onEnrollStudents,
  onDeactivate,
}: {
  cls: Class;
  teachers: UserType[];
  students: UserType[];
  onClose: () => void;
  onUpdateTeacher: (teacherId: string) => void;
  onEnrollStudents: (studentIds: string[]) => void;
  onDeactivate: () => void;
}) {
  const [selectedTeacherId, setSelectedTeacherId] = useState(
    cls.teacher_id || "",
  );
  const [isEnrollOpen, setIsEnrollOpen] = useState(false);
  const [selectedStudents, setSelectedStudents] = useState<string[]>([]);

  const handleTeacherChange = () => {
    if (selectedTeacherId !== cls.teacher_id) {
      onUpdateTeacher(selectedTeacherId);
    }
  };

  const toggleStudent = (studentId: string) => {
    setSelectedStudents((prev) =>
      prev.includes(studentId)
        ? prev.filter((id) => id !== studentId)
        : [...prev, studentId],
    );
  };

  const handleEnroll = () => {
    if (selectedStudents.length > 0) {
      onEnrollStudents(selectedStudents);
      setIsEnrollOpen(false);
      setSelectedStudents([]);
    }
  };

  const enrolledStudents = students.slice(0, 10);

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-80 bg-white border-l border-brand-border shadow-xl z-50 overflow-y-auto animate-in slide-in-from-right duration-200">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-display font-bold text-brand-ink">
              Class Details
            </h3>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-full"
              aria-label="Close"
            >
              <X className="w-5 h-5 text-brand-muted" />
            </button>
          </div>

          <div className="space-y-6">
            <div>
              <label className="block text-xs font-bold uppercase text-brand-muted mb-1">
                Class Name
              </label>
              <p className="text-brand-ink font-medium">{cls.name}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-brand-muted mb-1">
                  Subject
                </label>
                <p className="text-brand-ink font-medium">{cls.subject}</p>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-brand-muted mb-1">
                  Grade
                </label>
                <p className="text-brand-ink font-medium">Grade {cls.grade}</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-brand-muted mb-1">
                Teacher
              </label>
              <select
                value={selectedTeacherId}
                onChange={(e) => setSelectedTeacherId(e.target.value)}
                onBlur={handleTeacherChange}
                className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
              >
                <option value="">Unassigned</option>
                {teachers?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold uppercase text-brand-muted">
                  Enrolled Students
                </label>
                <button
                  onClick={() => setIsEnrollOpen(!isEnrollOpen)}
                  className="text-xs text-brand-primary hover:underline font-medium"
                >
                  + Enroll
                </button>
              </div>

              {isEnrollOpen && (
                <div className="mb-3 p-3 bg-brand-light rounded-lg border border-brand-mid">
                  <p className="text-xs text-brand-muted mb-2">
                    Select students to enroll:
                  </p>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {students.map((s) => (
                      <label
                        key={s.id}
                        className="flex items-center gap-2 text-sm text-brand-ink"
                      >
                        <input
                          type="checkbox"
                          checked={selectedStudents.includes(s.id)}
                          onChange={() => toggleStudent(s.id)}
                          className="rounded border-brand-border"
                        />
                        {s.first_name} {s.last_name}
                      </label>
                    ))}
                  </div>
                  {selectedStudents.length > 0 && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleEnroll}
                      className="mt-2 w-full"
                    >
                      Enroll {selectedStudents.length} student(s)
                    </Button>
                  )}
                </div>
              )}

              {enrolledStudents.length > 0 ? (
                <div className="space-y-2">
                  {enrolledStudents.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-brand-light text-brand-primary text-xs font-bold flex items-center justify-center">
                          {getInitials(s.first_name, s.last_name)}
                        </div>
                        <span className="text-sm text-brand-ink">
                          {s.first_name} {s.last_name}
                        </span>
                      </div>
                      <Badge variant="success">Active</Badge>
                    </div>
                  ))}
                  {students.length > 10 && (
                    <p className="text-xs text-brand-muted text-center">
                      +{students.length - 10} more students
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-brand-muted">
                  No students enrolled yet.
                </p>
              )}
            </div>

            <div className="pt-4 border-t border-brand-border">
              <Button
                variant="danger"
                size="sm"
                onClick={onDeactivate}
                className="w-full"
              >
                Deactivate class
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export function ClassManagement() {
  const { logout } = useAuth();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedClass, setSelectedClass] = useState<Class | null>(null);

  const { data: classes, isLoading: classesLoading } = useSchoolClasses();
  const { data: teachers } = useSchoolUsers("TEACHER");
  const { data: students } = useSchoolUsers("STUDENT");
  const updateClass = useUpdateClass();
  const enrollStudents = useEnrollStudents(selectedClass?.id || "");

  const handleUpdateTeacher = (teacherId: string) => {
    if (selectedClass) {
      updateClass.mutate({
        classId: selectedClass.id,
        teacher_id: teacherId || undefined,
      });
      setSelectedClass({ ...selectedClass, teacher_id: teacherId });
    }
  };

  const handleEnrollStudents = (studentIds: string[]) => {
    if (selectedClass) {
      enrollStudents.mutate({ student_ids: studentIds });
    }
  };

  const handleDeactivate = () => {
    if (selectedClass) {
      setSelectedClass(null);
    }
  };

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Classes"
      pageSubtitle="Manage classes, assign teachers, and enroll students"
      onLogout={logout}
      topNavAction={
        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus className="w-4 h-4 mr-1" />
          Create class
        </Button>
      }
    >
      <div className="space-y-6">
        <Card
          variant="default"
          className="bg-white border-role-school-border overflow-hidden"
        >
          {classesLoading ? (
            <div className="p-8 text-center text-brand-muted">Loading...</div>
          ) : classes && classes.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-brand-border text-left">
                    <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                      Class
                    </th>
                    <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                      Subject
                    </th>
                    <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                      Grade
                    </th>
                    <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                      Teacher
                    </th>
                    <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                      Students
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {classes.map((cls) => (
                    <tr
                      key={cls.id}
                      onClick={() => setSelectedClass(cls)}
                      className="border-b border-brand-border-soft last:border-0 hover:bg-brand-light/30 cursor-pointer"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <BookOpen className="w-4 h-4 text-brand-primary" />
                          <span className="text-sm font-medium text-brand-ink">
                            {cls.name}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-brand-body">
                        {cls.subject}
                      </td>
                      <td className="py-3 px-4 text-sm text-brand-body">
                        {cls.grade}
                      </td>
                      <td className="py-3 px-4 text-sm text-brand-body">
                        {cls.teacher_name || "Unassigned"}
                      </td>
                      <td className="py-3 px-4 text-sm text-brand-body">
                        {cls.student_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-brand-muted">
              No classes yet. Create your first class to get started.
            </div>
          )}
        </Card>

        <CreateClassModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onCreated={() => {}}
        />

        {selectedClass && (
          <ClassDetailPanel
            cls={selectedClass}
            teachers={teachers || []}
            students={students || []}
            onClose={() => setSelectedClass(null)}
            onUpdateTeacher={handleUpdateTeacher}
            onEnrollStudents={handleEnrollStudents}
            onDeactivate={handleDeactivate}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
