import { useState, useMemo } from "react";
import { Search } from "lucide-react";
import { StudentRow } from "./StudentRow";

export interface StudentRow {
  id: string;
  name: string;
  email: string;
  avgMastery: number | null;
  lastAssessedAt: string | null;
  dominantModality: string | null;
}

interface StudentsTableProps {
  students: StudentRow[];
  onStudentClick: (studentId: string) => void;
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

export function StudentsTable({
  students,
  onStudentClick,
  isLoading,
}: StudentsTableProps) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<
    "name" | "mastery-asc" | "mastery-desc" | "last-active"
  >("name");

  const filteredAndSorted = useMemo(() => {
    let result = [...students];
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q),
      );
    }
    if (sortBy === "name") {
      result.sort((a, b) => {
        const aLast = a.name.split(" ").slice(-1)[0] ?? a.name;
        const bLast = b.name.split(" ").slice(-1)[0] ?? b.name;
        return aLast.localeCompare(bLast);
      });
    } else if (sortBy === "mastery-asc") {
      result.sort((a, b) => (a.avgMastery ?? -1) - (b.avgMastery ?? -1));
    } else if (sortBy === "mastery-desc") {
      result.sort((a, b) => (b.avgMastery ?? -1) - (a.avgMastery ?? -1));
    } else if (sortBy === "last-active") {
      result.sort((a, b) => {
        if (!a.lastAssessedAt) return 1;
        if (!b.lastAssessedAt) return -1;
        return b.lastAssessedAt.localeCompare(a.lastAssessedAt);
      });
    }
    return result;
  }, [students, search, sortBy]);

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
          There are no students enrolled in this class yet.
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
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          aria-label="Sort students by"
          className="px-3 py-2 border border-brand-border rounded-xl text-sm text-brand-body bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary"
        >
          <option value="name">Name A–Z</option>
          <option value="mastery-asc">Mastery ↑</option>
          <option value="mastery-desc">Mastery ↓</option>
          <option value="last-active">Last active</option>
        </select>
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
                  Mastery
                </th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
                  Learning Style
                </th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
                  Last Assessed
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSorted.length > 0 ? (
                filteredAndSorted.map((student) => (
                  <StudentRow
                    key={student.id}
                    student={student}
                    onClick={() => onStudentClick(student.id)}
                  />
                ))
              ) : (
                <tr>
                  <td
                    colSpan={4}
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
