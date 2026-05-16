import { useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout, ClassGapMapTable } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { apiClient } from "@kaihle/auth";
import {
  useClassDetail,
  useClassEnrollments,
  useSchoolClasses,
  type EnrolledStudent,
} from "../hooks/useSchoolAdmin";
import { EditClassPanel } from "./EditClassPanel";
import { ManageEnrollmentsModal } from "./ManageEnrollmentsModal";

// ── Gap Map types ─────────────────────────────────────────────────────────────

interface StudentGapScore {
  student_id: string;
  student_name: string;
  mastery_score: number | null;
}

interface GapMapNode {
  subtopic_id: string;
  subtopic_name: string;
  topic_id: string;
  topic_name: string;
  grade_id: string;
  grade_name: string;
  grade_level: number;
  class_average: number | null;
  student_count: number;
  student_scores: StudentGapScore[];
}

interface ClassGapMap {
  class_id: string;
  subject_id: string;
  generated_at: string;
  nodes: GapMapNode[];
  has_student_data: boolean;
}

function useClassGapMap(classId: string, subjectId: string | undefined) {
  return useQuery({
    queryKey: ["class-gap-map", classId, subjectId],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/classes/${classId}/gap-map?subject_id=${subjectId}`,
      );
      return res.data as ClassGapMap;
    },
    enabled: !!classId && !!subjectId,
    staleTime: 5 * 60 * 1000,
  });
}

// ── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-white border border-role-school-border rounded-xl p-4 flex flex-col gap-1 min-w-0">
      <span className="text-xs font-bold uppercase tracking-wider text-role-school-muted">
        {label}
      </span>
      <span
        className={`font-sans text-3xl font-extrabold text-brand-ink leading-none ${accent ?? ""}`}
      >
        {value}
      </span>
      {sub && <span className="text-xs text-brand-muted">{sub}</span>}
    </div>
  );
}

function KpiCardSkeleton() {
  return (
    <div className="bg-white border border-role-school-border rounded-xl p-4 animate-pulse">
      <div className="h-3 w-20 bg-role-school-border rounded mb-3" />
      <div className="h-8 w-16 bg-role-school-border rounded" />
    </div>
  );
}

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab({
  diagnosticStatus,
  enrollments,
  enrollmentsLoading,
  onViewAllStudents,
}: {
  diagnosticStatus: "setup_needed" | "pending" | "has_data" | undefined;
  enrollments: EnrolledStudent[] | undefined;
  enrollmentsLoading: boolean;
  onViewAllStudents: () => void;
}) {
  const atRisk = (enrollments ?? [])
    .filter((s) => s.worst_mastery !== null && s.worst_mastery < 0.4)
    .sort((a, b) => (a.worst_mastery ?? 0) - (b.worst_mastery ?? 0));

  const showMore = atRisk.length > 5;
  const displayRisk = atRisk.slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Diagnostic status banner */}
      {diagnosticStatus === "pending" && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
          Students haven't completed the class diagnostic yet. Results will
          appear here once they do.
        </div>
      )}
      {diagnosticStatus === "setup_needed" && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
          No teacher assigned. Assign a teacher to enable the diagnostic.
        </div>
      )}

      {/* At-risk students */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-role-school-muted mb-3">
          At-risk students
        </h3>

        {enrollmentsLoading ? (
          <div className="animate-pulse space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-role-school-border rounded-lg" />
            ))}
          </div>
        ) : atRisk.length === 0 ? (
          <div className="bg-white border border-role-school-border rounded-xl p-6 text-center text-sm text-brand-muted">
            No students below the at-risk threshold.
          </div>
        ) : (
          <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-brand-surface-subtle border-b border-role-school-border">
                  {["Name", "Mastery"].map((h) => (
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
                {displayRisk.map((s) => {
                  const { dotClass, label } = getMasteryStyle(s.worst_mastery);
                  return (
                    <tr
                      key={s.id}
                      className="border-b border-brand-row-divider last:border-0"
                    >
                      <td className="px-4 py-3 text-sm font-semibold text-brand-ink">
                        {s.first_name} {s.last_name}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
                            aria-label={label}
                            role="img"
                          />
                          <span className="text-xs font-semibold text-brand-ink">
                            {s.worst_mastery !== null
                              ? `${Math.round(s.worst_mastery * 100)}%`
                              : "—"}
                          </span>
                          <span className="text-xs text-brand-muted">
                            {label}
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {showMore && (
              <div className="px-4 py-3 border-t border-role-school-border bg-brand-surface-subtle">
                <button
                  onClick={onViewAllStudents}
                  className="text-xs font-semibold text-brand-primary hover:underline"
                >
                  View all in Students tab →
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Students Tab ──────────────────────────────────────────────────────────────

function StudentsTab({
  enrollments,
  isLoading,
}: {
  enrollments: EnrolledStudent[] | undefined;
  isLoading: boolean;
}) {
  const sorted = [...(enrollments ?? [])].sort(
    (a, b) => (a.worst_mastery ?? 1) - (b.worst_mastery ?? 1),
  );

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-2">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-12 bg-role-school-border rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-brand-surface-subtle border-b border-role-school-border">
            {["Name", "Mastery", "Diagnostic"].map((h) => (
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
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={3}
                className="px-4 py-16 text-center text-sm text-brand-muted"
              >
                No students enrolled in this class yet.
              </td>
            </tr>
          ) : (
            sorted.map((s) => {
              const { dotClass, label } = getMasteryStyle(s.worst_mastery);
              return (
                <tr
                  key={s.id}
                  className="border-b border-brand-row-divider last:border-0"
                >
                  <td className="px-4 py-3 text-sm font-semibold text-brand-ink">
                    {s.first_name} {s.last_name}
                  </td>
                  <td className="px-4 py-3">
                    {s.worst_mastery === null ? (
                      <span className="text-xs text-brand-muted">Pending</span>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
                          aria-label={label}
                          role="img"
                        />
                        <span className="text-xs font-semibold text-brand-ink">
                          {Math.round(s.worst_mastery * 100)}%
                        </span>
                        <span className="text-xs text-brand-muted">
                          {label}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {s.diagnostic_completed ? (
                      <span className="text-xs font-semibold text-brand-green">
                        Done ✓
                      </span>
                    ) : (
                      <span className="text-xs text-brand-muted">Pending</span>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Gap Map Tab ───────────────────────────────────────────────────────────────

function GapMapTab({
  classId,
  subjectId,
  classDetailLoading,
}: {
  classId: string;
  subjectId: string | undefined;
  classDetailLoading: boolean;
}) {
  const { data, isLoading, isError } = useClassGapMap(classId, subjectId);

  if (classDetailLoading || (isLoading && !data)) {
    return (
      <div className="animate-pulse space-y-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-12 bg-role-school-border rounded" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-sm text-brand-red text-center">
        Could not load gap map. Please refresh.
      </div>
    );
  }

  if (!data) return null;

  if (!data.has_student_data) {
    return (
      <div className="bg-white rounded-2xl border border-role-school-border p-12 text-center">
        <span className="text-4xl mb-3 block" role="img" aria-label="chart">
          📊
        </span>
        <p className="font-display font-semibold text-brand-ink mb-2">
          No gap data yet
        </p>
        <p className="text-sm text-brand-muted">
          The gap map populates automatically once students complete the
          diagnostic.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-5 flex-wrap">
        {(
          [
            [0.8, "Strong"],
            [0.55, "Developing"],
            [0.2, "Needs Work"],
            [null, "Not assessed"],
          ] as Array<[number | null, string]>
        ).map(([score, label]) => {
          const { bgClass, textClass } = getMasteryStyle(score);
          return (
            <div key={label} className="flex items-center gap-1.5">
              <span
                className={`w-4 h-4 rounded ${bgClass}`}
                aria-hidden="true"
              />
              <span className={`text-xs font-medium ${textClass}`}>
                {label}
              </span>
            </div>
          );
        })}
      </div>
      <ClassGapMapTable nodes={data.nodes} variant="school-admin" />
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "students", label: "Students" },
  { key: "gap-map", label: "Gap Map" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function ClassDetailPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [enrollmentsModalOpen, setEnrollmentsModalOpen] = useState(false);

  const activeTab = (searchParams.get("tab") as TabKey | null) ?? "overview";

  const setTab = (tab: TabKey) => setSearchParams({ tab });

  const { data: allClasses } = useSchoolClasses();
  const classSummary = allClasses?.find((c) => c.id === classId);

  const {
    data: classDetail,
    isLoading: detailLoading,
    isError: detailError,
  } = useClassDetail(classId!);

  const { data: enrollments, isLoading: enrollmentsLoading } =
    useClassEnrollments(classId!);

  if (detailError) {
    return (
      <DashboardLayout variant="school-admin" pageTitle="Class">
        <div className="flex items-center justify-center py-24 text-sm font-semibold text-brand-red font-sans">
          Could not load class. Please refresh.
        </div>
      </DashboardLayout>
    );
  }

  const avgMastery = classSummary?.avg_mastery ?? null;
  const { label: masteryLabel } = getMasteryStyle(avgMastery);

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle={classDetail?.name ?? "Class"}
    >
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm mb-4">
        <button
          onClick={() => navigate("/school-admin/classes")}
          className="text-brand-muted font-semibold hover:text-brand-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded-sm"
        >
          Classes
        </button>
        <span className="text-brand-border">›</span>
        <span className="font-semibold text-brand-ink">
          {detailLoading ? (
            <span className="inline-block h-4 w-32 bg-role-school-border rounded animate-pulse" />
          ) : (
            classDetail?.name
          )}
        </span>
      </div>

      {/* Header */}
      {detailLoading ? (
        <div className="animate-pulse mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="h-8 w-48 bg-role-school-border rounded" />
            <div className="h-6 w-24 bg-role-school-border rounded-full" />
          </div>
          <div className="h-4 w-72 bg-role-school-border rounded mb-5" />
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <KpiCardSkeleton key={i} />
            ))}
          </div>
        </div>
      ) : (
        <div className="mb-6">
          <div className="flex items-start justify-between mb-1">
            <h1 className="font-display font-bold text-2xl text-brand-ink">
              {classDetail?.name}
            </h1>
            <div className="flex items-center gap-2 ml-4">
              <button
                onClick={() => setEnrollmentsModalOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold text-brand-primary bg-white border border-brand-primary rounded-lg hover:bg-brand-green-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
              >
                Manage enrollments
              </button>
              <button
                onClick={() => setEditPanelOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold text-white bg-brand-primary rounded-lg hover:bg-brand-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
              >
                Edit class
              </button>
            </div>
          </div>
          <p className="font-sans text-sm text-brand-muted mb-5">
            {[
              classDetail?.subject_name,
              classDetail?.grade_name,
              classDetail?.teacher_name,
              classDetail?.academic_year,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <KpiCard
              label="Students"
              value={classSummary?.student_count ?? "—"}
            />
            <KpiCard
              label="Avg Mastery"
              value={
                avgMastery !== null && avgMastery !== undefined
                  ? `${Math.round(avgMastery * 100)}%`
                  : "—"
              }
              sub={
                avgMastery !== null && avgMastery !== undefined
                  ? masteryLabel
                  : undefined
              }
            />
            <KpiCard
              label="At Risk"
              value={classSummary?.students_below_threshold ?? "—"}
              accent={
                (classSummary?.students_below_threshold ?? 0) > 0
                  ? "text-brand-red"
                  : undefined
              }
            />
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-role-school-border mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setTab(tab.key)}
            className={`px-4 pb-[10px] pt-1 text-sm font-semibold transition-colors border-b-2 -mb-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded-sm ${
              activeTab === tab.key
                ? "border-brand-primary text-brand-primary"
                : "border-transparent text-brand-muted hover:text-brand-body"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <OverviewTab
          diagnosticStatus={classSummary?.diagnostic_status}
          enrollments={enrollments}
          enrollmentsLoading={enrollmentsLoading}
          onViewAllStudents={() => setTab("students")}
        />
      )}
      {activeTab === "students" && (
        <StudentsTab enrollments={enrollments} isLoading={enrollmentsLoading} />
      )}
      {activeTab === "gap-map" && (
        <GapMapTab
          classId={classId!}
          subjectId={classDetail?.subject_id}
          classDetailLoading={detailLoading}
        />
      )}

      {editPanelOpen && (
        <EditClassPanel
          open={editPanelOpen}
          onClose={() => setEditPanelOpen(false)}
          classDetail={classDetail}
        />
      )}

      {enrollmentsModalOpen && (
        <ManageEnrollmentsModal
          open={enrollmentsModalOpen}
          onOpenChange={setEnrollmentsModalOpen}
          classId={classId!}
          className={classDetail?.name}
          gradeLevel={classSummary?.grade_level ?? null}
        />
      )}
    </DashboardLayout>
  );
}
