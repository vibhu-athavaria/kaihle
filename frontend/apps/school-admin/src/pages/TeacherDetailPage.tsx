import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useTeacherDetail } from "../hooks/useSchoolAdmin";
import { EditTeacherPanel } from "./EditTeacherPanel";

function initials(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

const SUBJECT_BADGE: Record<string, string> = {
  Mathematics: "bg-brand-primary text-white",
  "Integrated Science": "bg-violet-600 text-white",
  Biology: "bg-green-600 text-white",
  Chemistry: "bg-amber-600 text-white",
  Physics: "bg-blue-600 text-white",
  "English Language": "bg-red-600 text-white",
  "English Literature": "bg-purple-600 text-white",
};

function subjectBadgeClass(subject: string) {
  return SUBJECT_BADGE[subject] ?? "bg-gray-200 text-brand-ink";
}

export function TeacherDetailPage() {
  const { teacherId } = useParams<{ teacherId: string }>();
  const navigate = useNavigate();
  const [editPanelOpen, setEditPanelOpen] = useState(false);

  const {
    data: teacher,
    isLoading,
    isError,
  } = useTeacherDetail(teacherId ?? "");

  if (isLoading) {
    return (
      <DashboardLayout variant="school-admin" pageTitle="Teacher">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-role-school-border rounded-full w-1/3" />
          <div className="bg-white border border-role-school-border rounded-xl p-5 flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-role-school-border flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <div className="h-5 bg-role-school-border rounded-full w-1/4" />
              <div className="h-4 bg-role-school-border rounded-full w-1/3" />
            </div>
          </div>
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-role-school-border rounded-lg" />
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (isError || !teacher) {
    return (
      <DashboardLayout variant="school-admin" pageTitle="Teacher">
        <div className="flex items-center justify-center py-24 text-sm font-semibold text-brand-red font-sans">
          Failed to load teacher details. Please go back and try again.
        </div>
      </DashboardLayout>
    );
  }

  const isActive = teacher.is_active;
  const fullName = `${teacher.first_name} ${teacher.last_name}`;

  return (
    <DashboardLayout variant="school-admin" pageTitle={fullName}>
      {/* Breadcrumb */}
      <nav
        className="flex items-center gap-1.5 text-xs text-brand-muted mb-5"
        aria-label="Breadcrumb"
      >
        <button
          onClick={() => navigate("/school-admin/users")}
          className="hover:text-brand-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
        >
          Users
        </button>
        <span aria-hidden="true">›</span>
        <button
          onClick={() => navigate("/school-admin/users?tab=teachers")}
          className="hover:text-brand-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
        >
          Teachers
        </button>
        <span aria-hidden="true">›</span>
        <span className="text-brand-ink font-semibold">{fullName}</span>
      </nav>

      {/* Profile card */}
      <div className="bg-white border border-role-school-border rounded-xl p-5 flex items-center gap-4 mb-6">
        <div
          className={`w-14 h-14 rounded-full flex items-center justify-center text-white text-xl font-black flex-shrink-0 ${isActive ? "bg-brand-primary" : "bg-gray-300"}`}
          aria-label={`${fullName} initials`}
        >
          {initials(teacher.first_name, teacher.last_name)}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="font-display font-bold text-xl text-brand-ink leading-tight">
            {fullName}
          </h1>
          <p className="text-sm text-brand-body mt-0.5 truncate">
            {teacher.email}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          {isActive ? (
            <span className="text-xs font-bold rounded-full px-2 py-px bg-[#f0fdf4] text-brand-green">
              Active
            </span>
          ) : (
            <span className="text-xs font-bold rounded-full px-2 py-px bg-gray-100 text-brand-muted">
              Inactive
            </span>
          )}
          <span className="text-xs text-brand-muted font-sans">
            {teacher.assigned_classes.length}{" "}
            {teacher.assigned_classes.length === 1 ? "class" : "classes"}
          </span>
          <button
            onClick={() => setEditPanelOpen(true)}
            className="mt-1 px-3 py-1 text-xs font-semibold text-white bg-brand-primary rounded-lg hover:bg-brand-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            Edit teacher
          </button>
        </div>
      </div>

      {/* Assigned Classes */}
      <p className="text-xs font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
        Assigned Classes
      </p>

      <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
        {teacher.assigned_classes.length === 0 ? (
          <div className="py-12 text-center text-brand-muted text-sm">
            No classes assigned yet.
          </div>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[#fafcfa] border-b border-role-school-border">
                {["Class", "Subject", "Grade", "Students", "Avg Mastery"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-4 py-[10px] text-left text-xs font-black uppercase tracking-[0.7px] text-role-school-muted"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {teacher.assigned_classes.map((c) => {
                const { dotClass, label } = getMasteryStyle(c.avg_mastery);
                return (
                  <tr
                    key={c.class_id}
                    className="border-b border-[#f0f5ee] last:border-0"
                  >
                    <td className="px-4 py-[10px] text-sm font-bold text-brand-ink">
                      {c.class_name}
                    </td>
                    <td className="px-4 py-[10px]">
                      <span
                        className={`text-xs font-bold rounded-full px-2 py-px ${subjectBadgeClass(c.subject_name)}`}
                      >
                        {c.subject_name}
                      </span>
                    </td>
                    <td className="px-4 py-[10px] text-xs text-brand-body">
                      {c.grade_name || `Grade ${c.grade_level}`}
                    </td>
                    <td className="px-4 py-[10px] text-xs text-brand-body">
                      {c.student_count}
                    </td>
                    <td className="px-4 py-[10px]">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`}
                          aria-label={label}
                          role="img"
                        />
                        <span className="text-xs font-bold text-brand-ink">
                          {label}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {editPanelOpen && (
        <EditTeacherPanel
          open={editPanelOpen}
          onClose={() => setEditPanelOpen(false)}
          userId={teacherId ?? ""}
          initialValues={{
            first_name: teacher.first_name,
            last_name: teacher.last_name,
            email: teacher.email,
            is_active: teacher.is_active,
          }}
        />
      )}
    </DashboardLayout>
  );
}
