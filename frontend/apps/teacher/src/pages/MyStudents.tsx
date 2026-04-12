import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  useTeacherDashboard,
  TeacherClass,
} from "../hooks/useTeacherDashboard";
import { useMyStudents, StudentRow } from "../hooks/useMyStudents";
import { StudentsTable } from "../components/students/StudentsTable";
import { useAuth } from "@kaihle/auth";

function useClassStudents(classId: string | null, subjectId: string | null) {
  return useMyStudents(classId, subjectId);
}

export function MyStudentsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const schoolId = user?.school_id || null;
  const { data: dashboardData, isLoading: dashboardLoading } =
    useTeacherDashboard(schoolId);

  const classes: TeacherClass[] = dashboardData?.classes ?? [];
  const [filterClassId, setFilterClassId] = useState<string | null>(null);

  const classResults = classes.map((cls) =>
    useClassStudents(cls.id, cls.subjectId),
  );

  const allStudents = useMemo(() => {
    const seen = new Map<string, StudentRow>();
    for (const result of classResults) {
      if (result.data) {
        for (const s of result.data) {
          if (!seen.has(s.id)) seen.set(s.id, s);
        }
      }
    }
    return Array.from(seen.values());
  }, [classResults]);

  const isLoading = dashboardLoading || classResults.some((r) => r.isLoading);

  const handleStudentClick = (studentId: string) => {
    navigate(`/teacher/students/${studentId}/profile`);
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Students
        </h1>
        <p className="text-sm text-brand-muted">
          View student roster and mastery across all your classes
        </p>
      </div>

      {classes.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFilterClassId(null)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filterClassId === null
                ? "bg-brand-gold text-white"
                : "bg-white border border-brand-border text-brand-muted hover:text-brand-ink"
            }`}
          >
            All ({allStudents.length})
          </button>
          {classes.map((cls) => (
            <button
              key={cls.id}
              type="button"
              onClick={() => setFilterClassId(cls.id)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                filterClassId === cls.id
                  ? "bg-brand-gold text-white"
                  : "bg-white border border-brand-border text-brand-muted hover:text-brand-ink"
              }`}
            >
              {cls.name}
            </button>
          ))}
        </div>
      )}

      <StudentsTable
        students={allStudents}
        onStudentClick={handleStudentClick}
        isLoading={isLoading}
      />
    </div>
  );
}
