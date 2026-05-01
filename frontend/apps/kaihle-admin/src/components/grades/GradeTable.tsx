export interface GradeRow {
  id: string;
  name: string;
  level: number;
  description: string | null;
  is_active: boolean;
  curriculum_ids: string[];
  curriculum_names: string[];
}

interface CurriculumOption {
  id: string;
  name: string;
}

interface GradeTableProps {
  grades: GradeRow[];
  isLoading?: boolean;
  searchQuery: string;
  curriculumFilter: string;
  statusFilter: "ALL" | "active" | "inactive";
  onSearchChange: (value: string) => void;
  onCurriculumFilterChange: (value: string) => void;
  onStatusFilterChange: (value: "ALL" | "active" | "inactive") => void;
  onEditClick: (grade: GradeRow) => void;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  curricula?: CurriculumOption[];
}

export function GradeTable({
  grades,
  isLoading,
  searchQuery,
  curriculumFilter,
  statusFilter,
  onSearchChange,
  onCurriculumFilterChange,
  onStatusFilterChange,
  onEditClick,
  currentPage,
  totalPages,
  onPageChange,
  curricula = [],
}: GradeTableProps) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <div className="flex gap-3 animate-pulse">
            <div className="h-10 flex-1 bg-gray-200 rounded-xl" />
            <div className="h-10 w-36 bg-gray-200 rounded-xl" />
            <div className="h-10 w-36 bg-gray-200 rounded-xl" />
          </div>
        </div>
        <div className="divide-y divide-gray-50">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="px-4 py-4 flex items-center gap-4 animate-pulse"
            >
              <div className="w-8 h-8 rounded-full bg-gray-200" />
              <div className="h-4 w-24 bg-gray-200 rounded" />
              <div className="h-4 w-40 bg-gray-200 rounded" />
              <div className="h-4 w-20 bg-gray-200 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search grades..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="flex-1 bg-white border border-gray-200 rounded-xl px-4 py-2 text-sm font-['Inter'] placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
          />
          <select
            value={curriculumFilter}
            onChange={(e) => onCurriculumFilterChange(e.target.value)}
            className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm font-['Inter'] text-gray-600 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
          >
            <option value="ALL">All curricula</option>
            {curricula.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) =>
              onStatusFilterChange(
                e.target.value as "ALL" | "active" | "inactive",
              )
            }
            className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm font-['Inter'] text-gray-600 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
          >
            <option value="ALL">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Level
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Name
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Curricula
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Status
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {grades.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-gray-500">
                  <p className="font-['Inter'] text-sm">No grades found</p>
                </td>
              </tr>
            ) : (
              grades.map((grade) => (
                <tr
                  key={grade.id}
                  className="border-b border-gray-50 transition-colors cursor-pointer hover:bg-gray-50"
                  onClick={() => onEditClick(grade)}
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-brand-light flex items-center justify-center text-brand-primary text-xs font-medium">
                        {grade.level}
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="font-['Inter'] text-sm font-medium text-role-admin-ink">
                      {grade.name}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {grade.curriculum_names.length === 0 ? (
                      <span className="font-['Inter'] text-sm text-gray-400">
                        —
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {grade.curriculum_names.map((name) => (
                          <span
                            key={name}
                            className="rounded-full px-2.5 py-1 text-xs font-medium bg-green-50 text-green-700"
                          >
                            {name}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`w-2 h-2 rounded-full inline-block mr-2 ${
                        grade.is_active ? "bg-green-500" : "bg-gray-300"
                      }`}
                      aria-label={grade.is_active ? "Active" : "Inactive"}
                    />
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {grade.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      role="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditClick(grade);
                      }}
                      className="text-brand-primary text-sm font-medium font-['Inter'] cursor-pointer"
                    >
                      Edit →
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <span className="font-['Inter'] text-sm text-gray-600">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-['Inter'] text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px]"
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-['Inter'] text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px]"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
