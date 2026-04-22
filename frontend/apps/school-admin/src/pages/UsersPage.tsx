import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import {
  useSchoolStudents,
  useSchoolUsers,
  type StudentListItem,
} from "../hooks/useSchoolAdmin";

type Tab = "students" | "teachers" | "parents";
type StudentFilter = "all" | "attention" | "pending" | "not_logged_in";

function nameDisplay(first: string, last: string) {
  return `${first} ${last.charAt(0).toUpperCase()}.`;
}
function initials(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}
function diagnosticStatus(s: StudentListItem): "Completed" | "Pending" | null {
  if (s.diagnostic_completed) return "Completed";
  if (s.class_count > 0) return "Pending";
  return null;
}

export function UsersPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("students");
  const [filter, setFilter] = useState<StudentFilter>("all");

  const { data: students = [], isLoading: studentsLoading } =
    useSchoolStudents();
  const { data: teachers = [] } = useSchoolUsers("TEACHER");
  const { data: parents = [] } = useSchoolUsers("PARENT");

  const attentionCount = students.filter(
    (s) => s.worst_mastery !== null && s.worst_mastery < 0.4,
  ).length;
  const pendingCount = students.filter(
    (s) => !s.diagnostic_completed && s.class_count > 0,
  ).length;
  const notLoggedIn = students.filter((s) => !s.last_login_at).length;

  const filtered = students
    .filter((s) => {
      if (filter === "attention")
        return s.worst_mastery !== null && s.worst_mastery < 0.4;
      if (filter === "pending")
        return !s.diagnostic_completed && s.class_count > 0;
      if (filter === "not_logged_in") return !s.last_login_at;
      return true;
    })
    .sort((a, b) => {
      if (a.worst_mastery === null && b.worst_mastery === null) return 0;
      if (a.worst_mastery === null) return 1;
      if (b.worst_mastery === null) return -1;
      return a.worst_mastery - b.worst_mastery;
    });

  return (
    <DashboardLayout variant="school-admin" pageTitle="Users">
      <div className="flex border-b-2 border-role-school-border mb-4">
        {[
          { key: "students" as Tab, label: "Students", count: students.length },
          {
            key: "teachers" as Tab,
            label: "Teachers",
            count: (teachers as unknown[]).length,
          },
          {
            key: "parents" as Tab,
            label: "Parents",
            count: (parents as unknown[]).length,
          },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-5 py-2 text-[13px] font-bold border-b-[3px] -mb-[2px] transition-colors ${
              tab === key
                ? "text-brand-primary border-brand-primary"
                : "text-brand-muted border-transparent"
            }`}
          >
            {label}{" "}
            <span
              className={`inline-block rounded-full px-1.5 py-px text-[10px] font-black ml-1 ${
                tab === key
                  ? "bg-brand-green-light text-brand-primary"
                  : "bg-gray-100 text-brand-muted"
              }`}
            >
              {count}
            </span>
          </button>
        ))}
      </div>

      {tab === "students" && (
        <>
          <div className="flex items-center gap-3 mb-4 flex-wrap">
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
                className="text-xs outline-none font-sans bg-transparent w-40 placeholder:text-brand-muted"
                placeholder="Search students…"
              />
            </div>
            {[
              { key: "all" as StudentFilter, label: "All students" },
              {
                key: "attention" as StudentFilter,
                label: `Needs attention (${attentionCount})`,
                warn: true,
              },
              {
                key: "pending" as StudentFilter,
                label: `Diagnostic pending (${pendingCount})`,
              },
              {
                key: "not_logged_in" as StudentFilter,
                label: `Not yet logged in (${notLoggedIn})`,
              },
            ].map(({ key, label, warn }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-[5px] rounded-full text-[11px] font-semibold border transition-colors ${
                  filter === key
                    ? "bg-brand-primary text-white border-brand-primary"
                    : warn
                      ? "border-brand-amber text-brand-gold bg-[#fffbeb]"
                      : "bg-white border-role-school-border text-brand-body"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {studentsLoading ? (
            <div className="animate-pulse space-y-2">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="h-12 bg-role-school-border rounded-lg"
                />
              ))}
            </div>
          ) : (
            <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-[#fafcfa] border-b border-role-school-border">
                    {[
                      "Student",
                      "Classes",
                      "Lowest mastery",
                      "Diagnostic",
                      "Last active",
                      "",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-[10px] text-left text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s) => {
                    const { dotClass, label } = getMasteryStyle(
                      s.worst_mastery,
                    );
                    const isAtRisk =
                      s.worst_mastery !== null && s.worst_mastery < 0.4;
                    const diag = diagnosticStatus(s);
                    const lastActive = s.last_login_at
                      ? new Date(s.last_login_at).toLocaleDateString()
                      : "Never";
                    return (
                      <tr
                        key={s.id}
                        onClick={() =>
                          navigate(`/school-admin/users/students/${s.id}`)
                        }
                        className={`border-b border-[#f0f5ee] last:border-0 cursor-pointer transition-colors ${
                          isAtRisk
                            ? "bg-[#fffbeb] hover:bg-[#fef9c3]"
                            : "hover:bg-[#fafcfa]"
                        }`}
                      >
                        <td className="px-4 py-[10px]">
                          <div className="flex items-center gap-2.5">
                            <div
                              className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-black flex-shrink-0 ${isAtRisk ? "bg-brand-red" : "bg-brand-primary"}`}
                            >
                              {initials(s.first_name, s.last_name)}
                            </div>
                            <div className="text-[13px] font-bold text-brand-ink">
                              {nameDisplay(s.first_name, s.last_name)}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-[10px]">
                          <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-body">
                            <svg
                              className="w-3 h-3 text-brand-muted"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                            >
                              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                              <circle cx="9" cy="7" r="4" />
                            </svg>
                            {s.class_count}{" "}
                            {s.class_count === 1 ? "class" : "classes"}
                          </div>
                        </td>
                        <td className="px-4 py-[10px]">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`w-2 h-2 rounded-full ${dotClass}`}
                            />
                            <span
                              className={`text-xs font-bold ${
                                isAtRisk ? "text-brand-red" : "text-brand-ink"
                              }`}
                            >
                              {label}
                            </span>
                            {s.needs_work_class_count > 1 && (
                              <span className="text-[10px] text-brand-muted">
                                · {s.needs_work_class_count} classes
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-[10px]">
                          {diag && (
                            <span
                              className={`text-[10px] font-bold rounded-full px-2 py-px ${
                                diag === "Completed"
                                  ? "bg-[#f0fdf4] text-brand-green"
                                  : "bg-[#fffbeb] text-brand-gold"
                              }`}
                            >
                              {diag}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-[10px] text-[11px] text-brand-muted">
                          {lastActive}
                        </td>
                        <td className="px-4 py-[10px] text-brand-muted text-base">
                          ›
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div className="py-12 text-center text-brand-muted text-sm">
                  No students match this filter.
                </div>
              )}
            </div>
          )}
        </>
      )}
      {tab === "teachers" && (
        <div className="bg-white border border-role-school-border rounded-xl p-6 text-center text-brand-muted text-sm">
          Teachers tab — list and invite teachers.
        </div>
      )}
      {tab === "parents" && (
        <div className="bg-white border border-role-school-border rounded-xl p-6 text-center text-brand-muted text-sm">
          Parents tab — list parents and their linked students.
        </div>
      )}
    </DashboardLayout>
  );
}
