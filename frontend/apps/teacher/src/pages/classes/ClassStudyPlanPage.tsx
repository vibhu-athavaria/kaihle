import { Link, useParams } from "react-router-dom";
import { FileText } from "lucide-react";
import { useClass } from "../../hooks/useClass";
import { useClassEnrollments } from "../../hooks/useClassEnrollments";

export function ClassStudyPlanPage() {
  const { classId } = useParams<{ classId: string }>();
  const { data: currentClass } = useClass(classId);
  const { data: students = [], isLoading } = useClassEnrollments(classId);

  return (
    <div className="p-6">
      <nav
        className="flex items-center gap-2 text-sm text-brand-muted mb-4"
        aria-label="Breadcrumb"
      >
        <Link
          to="/teacher/classes"
          className="hover:text-brand-ink transition-colors"
        >
          Classes
        </Link>
        <span aria-hidden="true">/</span>
        <Link
          to={`/teacher/classes/${classId}`}
          className="hover:text-brand-ink transition-colors"
        >
          {currentClass?.name ?? "Class"}
        </Link>
        <span aria-hidden="true">/</span>
        <span className="text-brand-ink font-medium">Study Plans</span>
      </nav>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            Study Plans
          </h1>
          <p className="text-sm text-brand-muted mt-1">
            Study plans are generated per student from the Gap Map when a
            subtopic needs targeted support.
          </p>
        </div>
        <Link
          to={`/teacher/classes/${classId}/gap-map`}
          className="flex-shrink-0 ml-4 inline-flex items-center gap-1.5 bg-brand-gold text-white rounded-full px-4 py-2 text-xs font-bold hover:bg-brand-gold-dark transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
        >
          Open Gap Map →
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-14 bg-gray-100 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : students.length === 0 ? (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <FileText
            className="w-10 h-10 text-brand-muted mx-auto mb-3"
            aria-hidden="true"
          />
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-1">
            No students enrolled yet
          </h3>
          <p className="text-sm text-brand-muted max-w-xs mx-auto">
            Once students join this class and complete the diagnostic, you can
            assign study plans from the Gap Map.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-brand-border overflow-hidden">
          <table className="w-full" aria-label="Student study plans">
            <thead>
              <tr className="border-b border-brand-border bg-brand-border-soft">
                <th className="text-left px-5 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Student
                </th>
                <th className="text-left px-4 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Diagnostic
                </th>
                <th className="text-right px-5 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Plans
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border-soft">
              {students.map((student) => (
                <tr
                  key={student.id}
                  className="hover:bg-brand-border-soft/50 transition-colors"
                >
                  <td className="px-5 py-4">
                    <span className="text-sm font-sans font-medium text-brand-ink">
                      {student.first_name} {student.last_name}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    {student.diagnostic_completed ? (
                      <span className="text-xs font-medium text-brand-green">
                        Complete
                      </span>
                    ) : (
                      <span className="text-xs font-medium text-brand-muted">
                        Pending
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <Link
                      to={`/teacher/students/${student.id}/profile`}
                      className="text-xs font-sans font-bold text-brand-gold hover:text-brand-gold-dark transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
                    >
                      View plans →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
