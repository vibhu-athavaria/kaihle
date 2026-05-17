import { useState, useMemo } from "react";
import { Search, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

export interface StudentListItem {
  id: string;
  name: string;
  email: string;
  gradeName: string | null;
  classIds: string[];
  classNames: string[];
}

interface StudentListTableProps {
  students: StudentListItem[];
  isLoading?: boolean;
}

function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-14 bg-gray-100 rounded-lg" />
      ))}
    </div>
  );
}

export function StudentListTable({
  students,
  isLoading,
}: StudentListTableProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search) return students;
    const q = search.toLowerCase();
    return students.filter(
      (s) =>
        s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q),
    );
  }, [students, search]);

  if (isLoading) {
    return <TableSkeleton />;
  }

  if (students.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
        <div className="text-4xl mb-3">📋</div>
        <h3 className="font-display font-semibold text-brand-ink mb-1">
          No students yet
        </h3>
        <p className="text-sm text-brand-muted">
          There are no students enrolled in your classes yet.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-muted"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search students..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-brand-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-brand-border shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-brand-bg border-b border-brand-border">
                <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
                  Student
                </th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
                  Classes
                </th>
                <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.length > 0 ? (
                filtered.map((student) => (
                  <tr
                    key={student.id}
                    className="group hover:bg-brand-bg transition-colors"
                  >
                    <td className="px-4 py-3 border-b border-brand-border">
                      <div className="font-medium text-brand-ink group-hover:text-brand-primary transition-colors">
                        {student.name || "Unknown Student"}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {student.gradeName && (
                          <span className="text-xs font-semibold text-brand-gold">
                            {student.gradeName}
                          </span>
                        )}
                        <span className="text-xs text-brand-muted">
                          {student.email}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 border-b border-brand-border">
                      <div className="flex flex-wrap gap-1">
                        {student.classNames.map((name, i) => (
                          <span
                            key={student.classIds[i]}
                            className="px-2 py-0.5 bg-brand-bg text-brand-muted text-xs rounded-full"
                          >
                            {name}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 border-b border-brand-border text-right">
                      <button
                        type="button"
                        onClick={() =>
                          navigate(`/teacher/students/${student.id}/profile`)
                        }
                        className="inline-flex items-center gap-1 px-3 py-1.5 bg-brand-gold text-white text-sm font-medium rounded-lg hover:bg-brand-gold/90 transition-colors"
                      >
                        Detail
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-10 text-center text-sm text-brand-muted"
                  >
                    No students match your search.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
