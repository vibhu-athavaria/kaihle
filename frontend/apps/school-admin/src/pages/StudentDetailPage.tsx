import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DashboardLayout, StudentGapMapTab } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { apiClient, useAuth } from "@kaihle/auth";
import {
  useStudentAttempts,
  useStudentStudyPlans,
  type StudentProfile,
} from "../hooks/useSchoolAdmin";
import { EditStudentPanel } from "./EditStudentPanel";

function useStudentGapMap(
  studentId: string | undefined,
  subjectId: string | null,
) {
  return useQuery({
    queryKey: ["student-gap-map", studentId, subjectId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/students/${studentId}/gap-map?subject_id=${subjectId}`,
      );
      return res.data as {
        scores: Array<{
          subtopic_id: string;
          subtopic_name: string;
          topic_id: string;
          topic_name: string;
          mastery_score: number | null;
          last_assessed_at: string | null;
        }>;
      };
    },
    enabled: !!studentId && !!subjectId,
    staleTime: 5 * 60 * 1000,
  });
}

function nameDisplay(first: string, last: string) {
  return `${first} ${last.charAt(0).toUpperCase()}.`;
}
function initials(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

export function StudentDetailPage() {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [editPanelOpen, setEditPanelOpen] = useState(false);

  const {
    data: student,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["student", studentId, "detail"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}`);
      return res.data as StudentProfile;
    },
    enabled: !!studentId,
  });

  const { data: attempts = [] } = useStudentAttempts(studentId);
  const { data: studyPlans = [] } = useStudentStudyPlans(studentId);
  const activeStudyPlan = Array.isArray(studyPlans)
    ? studyPlans.find((p) => p.is_active)
    : null;

  // Derive unique subjects from enrollments for the subject selector
  const availableSubjects = (() => {
    const seen = new Set<string>();
    return (student?.class_enrollments ?? []).reduce<
      Array<{ subject_id: string; subject_name: string }>
    >((acc, ce) => {
      if (!seen.has(ce.subject_id)) {
        seen.add(ce.subject_id);
        acc.push({ subject_id: ce.subject_id, subject_name: ce.subject_name });
      }
      return acc;
    }, []);
  })();

  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    null,
  );
  const activeSubjectId =
    selectedSubjectId ?? availableSubjects[0]?.subject_id ?? null;
  const { data: gapMap } = useStudentGapMap(studentId, activeSubjectId);

  const needsWorkClassCount = (student?.class_enrollments ?? []).filter(
    (ce) => {
      const scores = ce.gap_states
        .map((g) => g.mastery_score)
        .filter((s): s is number => s !== null);
      const avg = scores.length
        ? scores.reduce((a, b) => a + b, 0) / scores.length
        : null;
      return avg !== null && avg < 0.4;
    },
  ).length;

  if (isError)
    return (
      <DashboardLayout
        variant="school-admin"
        pageTitle="Student Detail"
        permissions={user?.permissions}
      >
        <div className="flex items-center justify-center py-24 text-sm font-semibold text-brand-red font-sans">
          Failed to load data. Please refresh the page.
        </div>
      </DashboardLayout>
    );

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Student Detail"
      permissions={user?.permissions}
    >
      <div className="flex items-center gap-2 text-sm mb-5">
        <button
          onClick={() => navigate("/school-admin/users")}
          className="text-brand-muted font-semibold hover:text-brand-primary transition-colors"
        >
          Users
        </button>
        <span className="text-brand-border">›</span>
        <button
          onClick={() => navigate("/school-admin/users")}
          className="text-brand-muted font-semibold hover:text-brand-primary transition-colors"
        >
          Students
        </button>
        <span className="text-brand-border">›</span>
        <span className="font-display font-bold text-brand-ink text-sm">
          {student
            ? nameDisplay(student.first_name, student.last_name)
            : "Loading…"}
        </span>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="h-20 bg-role-school-border rounded-xl" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-48 bg-role-school-border rounded-xl" />
            <div className="h-48 bg-role-school-border rounded-xl" />
          </div>
        </div>
      ) : !student ? null : (
        <>
          <div className="bg-white border border-role-school-border rounded-xl p-5 flex items-center gap-4 mb-5">
            <div className="w-12 h-12 rounded-full bg-brand-red flex items-center justify-center text-white text-base font-black flex-shrink-0">
              {initials(student.first_name, student.last_name)}
            </div>
            <div>
              <div className="font-display font-bold text-lg text-brand-ink">
                {student.first_name} {student.last_name.charAt(0).toUpperCase()}
                .
              </div>
              <div className="text-xs text-brand-muted mt-0.5">
                {student.grade_name ??
                  (student.grade_level !== null &&
                  student.grade_level !== undefined
                    ? `Grade ${student.grade_level}`
                    : "No grade")}{" "}
                · {student.curriculum_name} · Enrolled{" "}
                {new Date(student.enrolled_at).toLocaleDateString("en-GB", {
                  month: "short",
                  year: "numeric",
                })}
              </div>
            </div>
            <div className="ml-auto flex items-center gap-4">
              <button
                onClick={() => setEditPanelOpen(true)}
                className="px-4 py-2 bg-brand-primary text-white text-sm font-semibold rounded-lg hover:bg-brand-primary/90 transition-colors"
              >
                Edit student
              </button>
              <div className="flex gap-6">
                <div className="text-center">
                  <div className="font-display font-bold text-xl text-brand-ink">
                    {student.class_enrollments.length}
                  </div>
                  <div className="text-xs font-black uppercase tracking-[0.5px] text-brand-muted">
                    Classes
                  </div>
                </div>
                <div className="text-center">
                  <div
                    className={`font-display font-bold text-xl ${needsWorkClassCount > 0 ? "text-brand-red" : "text-brand-ink"}`}
                  >
                    {needsWorkClassCount}
                  </div>
                  <div className="text-xs font-black uppercase tracking-[0.5px] text-brand-muted">
                    Needs Work
                  </div>
                </div>
                <div className="text-center">
                  <div className="font-display font-bold text-xl text-brand-ink">
                    {attempts.length}
                  </div>
                  <div className="text-xs font-black uppercase tracking-[0.5px] text-brand-muted">
                    Assessments
                  </div>
                </div>
                <div className="text-center">
                  <div className="font-display font-bold text-xl text-brand-ink">
                    {student.last_login_at
                      ? new Date(student.last_login_at).toLocaleDateString(
                          "en-GB",
                          { day: "numeric", month: "short" },
                        )
                      : "Never"}
                  </div>
                  <div className="text-xs font-black uppercase tracking-[0.5px] text-brand-muted">
                    Last active
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mb-5">
            <div className="text-xs font-black uppercase tracking-[0.8px] text-role-school-muted mb-3">
              Gap Map
            </div>
            {availableSubjects.length > 1 && (
              <div className="flex gap-2 mb-4 flex-wrap">
                {availableSubjects.map((s) => (
                  <button
                    key={s.subject_id}
                    type="button"
                    onClick={() => setSelectedSubjectId(s.subject_id)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      activeSubjectId === s.subject_id
                        ? "bg-brand-light text-brand-primary border border-brand-primary"
                        : "bg-gray-100 text-brand-muted hover:bg-gray-200"
                    }`}
                  >
                    {s.subject_name}
                  </button>
                ))}
              </div>
            )}
            <StudentGapMapTab scores={gapMap?.scores ?? []} />
          </div>

          {activeStudyPlan && (
            <div className="mb-5">
              <div className="text-xs font-black uppercase tracking-[0.8px] text-role-school-muted mb-3">
                Study plan
              </div>
              <div className="bg-white border border-role-school-border rounded-xl p-4 flex items-center gap-4">
                <div className="w-9 h-9 rounded-lg bg-[#f0fdf4] flex items-center justify-center flex-shrink-0">
                  <svg
                    className="w-4 h-4 text-brand-primary"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                  </svg>
                </div>
                <div>
                  <div className="text-sm font-bold text-brand-ink">
                    {activeStudyPlan.title ?? "Active study plan"}
                  </div>
                  <div className="text-xs text-brand-muted mt-0.5">
                    Assigned{" "}
                    {activeStudyPlan.assigned_at
                      ? new Date(
                          activeStudyPlan.assigned_at,
                        ).toLocaleDateString()
                      : "—"}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-xs font-bold text-brand-primary">
                  <span className="w-2 h-2 rounded-full bg-brand-primary" />
                  Active
                </div>
              </div>
            </div>
          )}

          <div>
            <div className="text-xs font-black uppercase tracking-[0.8px] text-role-school-muted mb-3">
              Recent assessments
            </div>
            <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-[#fafcfa] border-b border-role-school-border">
                    {["Assessment", "Class", "Date", "Score", "Type"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-4 py-[9px] text-left text-xs font-black uppercase tracking-[0.7px] text-role-school-muted"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {attempts.slice(0, 8).map((a, i) => {
                    const { label, bgClass, textClass } = getMasteryStyle(
                      a.score,
                    );
                    return (
                      <tr
                        key={i}
                        className="border-b border-[#f0f5ee] last:border-0"
                      >
                        <td className="px-4 py-[9px] text-xs font-bold text-brand-ink">
                          {a.assessment_name ?? "Assessment"}
                        </td>
                        <td className="px-4 py-[9px] text-xs text-brand-muted">
                          {a.class_name ?? "—"}
                        </td>
                        <td className="px-4 py-[9px] text-xs text-brand-muted">
                          {a.completed_at
                            ? new Date(a.completed_at).toLocaleDateString()
                            : "—"}
                        </td>
                        <td className="px-4 py-[9px]">
                          <span
                            className={`text-xs font-bold rounded-full px-2 py-px ${bgClass} ${textClass}`}
                          >
                            {label}
                          </span>
                        </td>
                        <td className="px-4 py-[9px] text-xs text-brand-muted capitalize">
                          {(a.assessment_type ?? "")
                            .toLowerCase()
                            .replace("_", " ")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {attempts.length === 0 && (
                <div className="py-10 text-center text-brand-muted text-sm">
                  No assessments yet.
                </div>
              )}
            </div>
          </div>

          {editPanelOpen && (
            <EditStudentPanel
              open={editPanelOpen}
              onClose={() => setEditPanelOpen(false)}
              student={student}
            />
          )}
        </>
      )}
    </DashboardLayout>
  );
}
