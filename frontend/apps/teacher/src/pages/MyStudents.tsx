import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import {
  useTeacherDashboard,
  TeacherClass,
} from "../hooks/useTeacherDashboard";
import { useMyStudents } from "../hooks/useMyStudents";
import { StudentsTable } from "../components/students/StudentsTable";
import { useAuth } from "@kaihle/auth";

export function MyStudentsPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const schoolId = user?.school_id || null;
  const { data: dashboardData } = useTeacherDashboard(schoolId);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(
    classId ?? null,
  );

  const classes: TeacherClass[] = dashboardData?.classes ?? [];
  const selectedClass = classes.find(
    (c: TeacherClass) => c.id === selectedClassId,
  );
  const subjectId = selectedClass?.subjectId ?? null;
  const {
    data: students,
    isLoading,
    isError,
  } = useMyStudents(selectedClassId, subjectId);

  const handleStudentClick = (studentId: string) => {
    navigate(`/teacher/students/${studentId}/profile`);
  };

  return (
    <div className="p-6 space-y-6">
      <Link
        to="/teacher/dashboard"
        className="inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded"
      >
        <ChevronLeft className="w-4 h-4" aria-hidden="true" />
        Back to dashboard
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            My Students
          </h1>
          <p className="text-sm text-brand-muted">
            View student roster and mastery for your classes
          </p>
        </div>
        {classes.length > 1 && (
          <select
            value={selectedClassId ?? ""}
            onChange={(e) => setSelectedClassId(e.target.value || null)}
            className="px-3 py-2 border border-brand-border rounded-lg text-sm text-brand-ink bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary"
          >
            <option value="">Select a class</option>
            {classes.map((cls: TeacherClass) => (
              <option key={cls.id} value={cls.id}>
                {cls.name} — {cls.subjectName}
              </option>
            ))}
          </select>
        )}
      </div>

      {isError && (
        <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm">
          Failed to load student data. Please try again.
        </div>
      )}

      {selectedClassId ? (
        <StudentsTable
          students={students ?? []}
          onStudentClick={handleStudentClick}
          isLoading={isLoading}
        />
      ) : (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-3">📋</div>
          <h3 className="font-display font-semibold text-brand-ink mb-1">
            Select a class
          </h3>
          <p className="text-sm text-brand-muted">
            Choose a class from the dropdown above to view your student roster.
          </p>
        </div>
      )}
    </div>
  );
}
