import { useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolClasses, type ClassSummary } from "../hooks/useSchoolAdmin";

export function ClassManagement() {
  const navigate = useNavigate();
  const { data: classes = [], isLoading, isError } = useSchoolClasses();
  const [filter, setFilter] = useState<"all" | "attention">("all");
  const [gradeFilter, setGradeFilter] = useState<number | null>(null);
  const [subjectFilter, setSubjectFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const attentionCount = classes.filter(
    (c) => c.diagnostic_status !== "has_data",
  ).length;

  const filtered = classes
    .filter((c) => {
      if (filter === "attention") return c.diagnostic_status !== "has_data";
      return true;
    })
    .filter((c) => gradeFilter === null || c.grade_level === gradeFilter)
    .filter((c) => subjectFilter === null || c.subject_name === subjectFilter)
    .filter(
      (c) =>
        !searchQuery ||
        c.name.toLowerCase().includes(searchQuery.toLowerCase()),
    );

  const grades = [...new Set(classes.map((c) => c.grade_level))].sort();
  const subjects = [...new Set(classes.map((c) => c.subject_name))].sort();

  if (isLoading)
    return (
      <DashboardLayout variant="school-admin" pageTitle="Classes">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-role-school-border rounded-lg" />
          ))}
        </div>
      </DashboardLayout>
    );

  if (isError)
    return (
      <DashboardLayout variant="school-admin" pageTitle="Classes">
        <div className="flex items-center justify-center py-24 text-sm font-semibold text-brand-red font-sans">
          Failed to load data. Please refresh the page.
        </div>
      </DashboardLayout>
    );

  return (
    <DashboardLayout variant="school-admin" pageTitle="Classes">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 bg-white border border-role-school-border rounded-lg px-3 py-[7px]">
            <svg
              className="w-3 h-3 text-brand-muted"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs outline-none font-sans bg-transparent text-brand-ink placeholder:text-brand-muted w-40"
              placeholder="Search classes…"
              aria-label="Search classes"
            />
          </div>
          <button
            onClick={() =>
              setFilter(filter === "attention" ? "all" : "attention")
            }
            className={`px-3 py-[5px] rounded-full text-xs font-semibold border transition-colors ${
              filter === "attention"
                ? "bg-brand-primary text-white border-brand-primary"
                : "bg-white text-brand-body border-role-school-border"
            }`}
          >
            Needs attention {attentionCount > 0 && `(${attentionCount})`}
          </button>
          <select
            onChange={(e) =>
              setGradeFilter(e.target.value ? Number(e.target.value) : null)
            }
            className="px-3 py-[5px] rounded-full text-xs font-semibold border border-role-school-border bg-white text-brand-body outline-none"
          >
            <option value="">All grades</option>
            {grades.map((g) => (
              <option key={g} value={g}>
                Grade {g}
              </option>
            ))}
          </select>
          <select
            onChange={(e) => setSubjectFilter(e.target.value || null)}
            className="px-3 py-[5px] rounded-full text-xs font-semibold border border-role-school-border bg-white text-brand-body outline-none"
          >
            <option value="">All subjects</option>
            {subjects.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span className="text-xs text-brand-muted">
            {filtered.length} classes
          </span>
        </div>
        <button className="bg-brand-primary text-white rounded-full px-4 py-[6px] text-xs font-bold flex items-center gap-1">
          <svg
            className="w-3 h-3"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New class
        </button>
      </div>

      <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-[#fafcfa] border-b border-role-school-border">
              {[
                "Class",
                "Subject",
                "Grade",
                "Teacher",
                "Mastery",
                "Students",
                "",
              ].map((h) => (
                <th
                  key={h}
                  className="px-4 py-[10px] text-left text-xs font-black uppercase tracking-[0.7px] text-role-school-muted"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <ClassRow
                key={c.id}
                cls={c}
                onClick={() =>
                  navigate(`/school-admin/classes/${c.id}/gap-map`)
                }
              />
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-16 text-center text-brand-muted text-sm">
            No classes match this filter.
          </div>
        )}
      </div>

      <div className="flex gap-5 mt-3 px-1">
        {[
          { dotClass: "bg-brand-red", label: "Needs Work" },
          { dotClass: "bg-brand-amber", label: "Developing" },
          { dotClass: "bg-brand-green", label: "Strong" },
          {
            dotClass: "border-[1.5px] border-gray-300 bg-transparent",
            label: "Diagnostic pending",
          },
          {
            dotClass: "bg-[#fffbeb] border-[1.5px] border-brand-amber",
            label: "Setup needed",
          },
        ].map(({ dotClass, label }) => (
          <div
            key={label}
            className="flex items-center gap-1.5 text-xs text-brand-body font-semibold"
          >
            <span
              className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
            />
            {label}
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}

function ClassRow({
  cls,
  onClick,
}: {
  cls: ClassSummary;
  onClick: () => void;
}) {
  const isSetup = cls.diagnostic_status === "setup_needed";
  const isPending = cls.diagnostic_status === "pending";
  const { dotClass, label } = getMasteryStyle(cls.avg_mastery);

  function handleKeyDown(e: KeyboardEvent<HTMLTableRowElement>) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  }

  return (
    <tr
      onClick={onClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`View gap map for ${cls.name}`}
      className={`border-b border-[#f0f5ee] cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-inset ${
        isSetup ? "bg-[#fffbeb] hover:bg-[#fef9c3]" : "hover:bg-[#fafcfa]"
      }`}
    >
      <td className="px-4 py-3 font-bold text-sm text-brand-ink">{cls.name}</td>
      <td className="px-4 py-3 text-xs font-semibold text-brand-body">
        {cls.subject_name}
      </td>
      <td className="px-4 py-3 text-xs text-brand-muted">
        Grade {cls.grade_level}
      </td>
      <td className="px-4 py-3">
        {isSetup ? (
          <span className="flex items-center gap-1.5 text-xs font-bold text-brand-amber">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            Assign teacher
          </span>
        ) : (
          <span className="text-xs text-brand-body">{cls.teacher_name}</span>
        )}
      </td>
      <td className="px-4 py-3">
        {isPending ? (
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full border-[1.5px] border-gray-300" />
            <span className="text-xs text-brand-muted">Diagnostic pending</span>
          </div>
        ) : isSetup ? (
          <span className="text-brand-muted">—</span>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
            <span className="text-xs font-semibold text-brand-ink">
              {label}
            </span>
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-brand-muted">
        {cls.student_count}
      </td>
      <td className="px-4 py-3 text-brand-muted text-base">›</td>
    </tr>
  );
}
