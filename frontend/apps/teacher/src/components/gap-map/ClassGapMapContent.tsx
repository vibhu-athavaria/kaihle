import { useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { getMasteryStyle } from "@kaihle/types";
import { ClassGapMapTable } from "@kaihle/ui";
import { useClassGapMap } from "../../hooks/useClassGapMap";
import { useClass } from "../../hooks/useClass";
import { useClassAssessments } from "../../hooks/useClassAssessments";
import { useClassEnrollments } from "../../hooks/useClassEnrollments";
import { LearningProfileSidePanel } from "./LearningProfileSidePanel";

const LEGEND_SCORES: Array<[number | null, string]> = [
  [0.8, "Strong"],
  [0.55, "Developing"],
  [0.2, "Needs Work"],
  [null, "Not assessed"],
];

interface ClassGapMapContentProps {
  classId: string;
  showExport?: boolean;
}

export function ClassGapMapContent({
  classId,
  showExport = true,
}: ClassGapMapContentProps) {
  const { data: currentClass } = useClass(classId);
  const subjectId = currentClass?.subject_id ?? null;

  const { data: assessments } = useClassAssessments(classId);
  const { data: enrollments = [] } = useClassEnrollments(classId);
  const { data, isLoading, isError } = useClassGapMap(classId, subjectId);

  const hasDiagnostic =
    assessments?.some((a) => a.assessment_type === "DIAGNOSTIC") ?? false;
  const hasAnyStudentData = data?.has_student_data ?? false;

  const completedCount = enrollments.filter(
    (e) => e.diagnostic_completed,
  ).length;
  const totalCount = enrollments.length;
  const pendingCount = totalCount - completedCount;

  const [selectedStudent, setSelectedStudent] = useState<{
    studentId: string;
    studentName: string;
    subtopicScores: Array<{
      subtopicName: string;
      topicName: string;
      masteryScore: number | null;
    }>;
  } | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const handleCellClick = (studentId: string, studentName: string) => {
    const subtopicScores =
      data?.nodes?.map((n: any) => {
        const score = n.student_scores.find(
          (s: any) => s.student_id === studentId,
        );
        return {
          subtopicName: n.subtopic_name,
          topicName: n.topic_name,
          masteryScore: score?.mastery_score ?? null,
        };
      }) ?? [];
    setSelectedStudent({ studentId, studentName, subtopicScores });
    setPanelOpen(true);
  };

  const handleExportCsv = () => {
    if (!data?.nodes || !currentClass) return;
    const rows: string[][] = [
      ["Student", "Topic", "Subtopic", "Mastery %", "Last Assessed"],
    ];
    for (const node of data.nodes) {
      for (const score of node.student_scores) {
        rows.push([
          score.student_name,
          node.topic_name,
          node.subtopic_name,
          score.mastery_score !== null
            ? `${Math.round(score.mastery_score * 100)}`
            : "—",
          score.last_assessed_at
            ? new Date(score.last_assessed_at).toLocaleDateString("en-GB")
            : "—",
        ]);
      }
    }
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gap-map-${(currentClass.name ?? "class").replace(/\s+/g, "-")}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Title + submission counter + export */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="font-display font-bold text-xl text-brand-ink">
            Gap Map
          </h2>
          <p className="text-sm text-brand-muted mt-0.5">
            {currentClass
              ? `${currentClass.name} — ${currentClass.subject_name}`
              : "Class mastery heatmap by subtopic"}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {hasDiagnostic && totalCount > 0 && (
            <div className="text-right">
              <p className="text-sm font-semibold text-brand-ink">
                {completedCount} of {totalCount} students
              </p>
              <p className="text-xs text-brand-muted">
                {pendingCount > 0
                  ? `${pendingCount} yet to submit diagnostic`
                  : "All students submitted"}
              </p>
            </div>
          )}
          {showExport && hasAnyStudentData && (
            <button
              type="button"
              onClick={handleExportCsv}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-muted hover:text-brand-ink border border-brand-border rounded-lg transition-colors"
            >
              <Download className="w-4 h-4" aria-hidden="true" />
              Export CSV
            </button>
          )}
        </div>
      </div>

      {isError && (
        <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm">
          Failed to load gap map data. Please try again.
        </div>
      )}

      {isLoading && (
        <div className="animate-pulse space-y-2">
          <div className="h-8 bg-gray-100 rounded w-1/4 mb-4" />
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-14 bg-gray-100 rounded-lg" />
          ))}
        </div>
      )}

      {!isLoading && data && !hasAnyStudentData && !hasDiagnostic && (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <span className="text-4xl mb-3 block" role="img" aria-label="chart">
            📊
          </span>
          <p className="font-display font-semibold text-brand-ink mb-2">
            No gap data yet
          </p>
          <p className="text-sm text-brand-muted mb-4">
            Design a Tier 1 Diagnostic first — the Gap Map populates
            automatically once students complete it.
          </p>
          <Link
            to={`/teacher/classes/${classId}`}
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark rounded transition-colors"
          >
            Design diagnostic →
          </Link>
        </div>
      )}

      {!isLoading && data && !hasAnyStudentData && hasDiagnostic && (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <span
            className="text-4xl mb-3 block"
            role="img"
            aria-label="hourglass"
          >
            ⏳
          </span>
          <p className="font-display font-semibold text-brand-ink mb-2">
            Waiting for students to complete the diagnostic
          </p>
          <p className="text-sm text-brand-muted">
            Results will appear here automatically as students submit.
          </p>
          {pendingCount > 0 && totalCount > 0 && (
            <p className="text-xs text-brand-muted mt-3">
              {pendingCount} of {totalCount} students yet to submit
            </p>
          )}
        </div>
      )}

      {data && hasAnyStudentData && (
        <>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-5">
              {LEGEND_SCORES.map(([score, label]) => {
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
            <p className="text-xs text-brand-muted italic">
              Click any cell to view that student's full learning profile
            </p>
          </div>

          {pendingCount > 0 && (
            <p className="text-xs text-brand-muted">
              {pendingCount} student{pendingCount !== 1 ? "s" : ""} yet to
              submit — their columns will appear once they complete the
              diagnostic.
            </p>
          )}

          <ClassGapMapTable
            nodes={data.nodes}
            variant="teacher"
            onCellClick={handleCellClick}
          />
        </>
      )}

      <LearningProfileSidePanel
        open={panelOpen}
        onOpenChange={setPanelOpen}
        studentId={selectedStudent?.studentId ?? null}
        studentName={selectedStudent?.studentName ?? null}
        subtopicScores={selectedStudent?.subtopicScores ?? []}
      />
    </div>
  );
}
