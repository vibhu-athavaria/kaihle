import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
import { useClassGapMap } from "../../hooks/useClassGapMap";
import { useClass } from "../../hooks/useClass";
import { useClassAssessments } from "../../hooks/useClassAssessments";
import { useClassEnrollments } from "../../hooks/useClassEnrollments";
import { LearningProfileSidePanel } from "./LearningProfileSidePanel";

function HeatCell({
  score,
  label: ariaLabel,
  onClick,
  variant = "default",
}: {
  score: number | null;
  label: string;
  onClick?: () => void;
  variant?: "default" | "summary";
}) {
  const { bgClass, textClass, label } = getMasteryStyle(score);
  const pct = scoreToPercent(score);

  const baseClass = [
    "w-full h-14 flex flex-col items-center justify-center gap-0.5 rounded select-none",
    bgClass,
    textClass,
    variant === "summary" ? "ring-1 ring-inset ring-black/10" : "",
  ].join(" ");

  if (!onClick) {
    return (
      <div className={baseClass} aria-label={ariaLabel}>
        {score !== null ? (
          <>
            <span className="text-sm font-bold leading-none">{pct}</span>
            <span className="text-[10px] font-medium leading-none opacity-70">
              {label}
            </span>
          </>
        ) : (
          <span className="text-xs font-medium opacity-40">—</span>
        )}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className={[
        baseClass,
        "transition-all hover:scale-[1.06] hover:shadow-lg hover:z-10 relative",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1",
      ].join(" ")}
    >
      {score !== null ? (
        <>
          <span className="text-sm font-bold leading-none">{pct}</span>
          <span className="text-[10px] font-medium leading-none opacity-70">
            {label}
          </span>
        </>
      ) : (
        <span className="text-xs font-medium opacity-40">—</span>
      )}
    </button>
  );
}

function AvgBadge({ score }: { score: number | null }) {
  const { bgClass, textClass } = getMasteryStyle(score);
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${bgClass} ${textClass}`}
    >
      {score !== null ? scoreToPercent(score) : "—"}
    </span>
  );
}

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

  const studentMap = new Map<string, string>();
  data?.nodes?.forEach((n: any) =>
    n.student_scores.forEach((s: any) =>
      studentMap.set(s.student_id, s.student_name),
    ),
  );
  const students = Array.from(studentMap.entries()).map(([id, name]) => ({
    student_id: id,
    student_name: name,
  }));

  type TopicGroup = { topicId: string; topicName: string; nodes: any[] };
  type GradeGroup = {
    gradeId: string;
    gradeName: string;
    topics: TopicGroup[];
  };

  const gradeGroups: GradeGroup[] = [];
  const gradeIndexMap = new Map<string, number>();
  const topicIndexMap = new Map<string, number>();

  data?.nodes?.forEach((n: any) => {
    if (!gradeIndexMap.has(n.grade_id)) {
      gradeIndexMap.set(n.grade_id, gradeGroups.length);
      gradeGroups.push({
        gradeId: n.grade_id,
        gradeName: n.grade_name,
        topics: [],
      });
    }
    const gradeGroup = gradeGroups[gradeIndexMap.get(n.grade_id)!];
    const topicKey = `${n.grade_id}:${n.topic_id}`;
    if (!topicIndexMap.has(topicKey)) {
      topicIndexMap.set(topicKey, gradeGroup.topics.length);
      gradeGroup.topics.push({
        topicId: n.topic_id,
        topicName: n.topic_name,
        nodes: [],
      });
    }
    gradeGroup.topics[topicIndexMap.get(topicKey)!].nodes.push(n);
  });

  const topicClassAvg = (nodes: any[]): number | null => {
    const avgs = nodes
      .map((n: any) => n.class_average)
      .filter((x: number | null): x is number => x !== null);
    return avgs.length > 0
      ? avgs.reduce((a: number, b: number) => a + b, 0) / avgs.length
      : null;
  };

  const studentOverallAvg = (studentId: string): number | null => {
    const scores =
      data?.nodes
        ?.map(
          (n: any) =>
            n.student_scores.find((s: any) => s.student_id === studentId)
              ?.mastery_score ?? null,
        )
        .filter((x: number | null): x is number => x !== null) ?? [];
    return scores.length > 0
      ? scores.reduce((a: number, b: number) => a + b, 0) / scores.length
      : null;
  };

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
  const [collapsedGrades, setCollapsedGrades] = useState<Set<string>>(
    new Set(),
  );

  function toggleGrade(gradeId: string) {
    setCollapsedGrades((prev) => {
      const next = new Set(prev);
      if (next.has(gradeId)) next.delete(gradeId);
      else next.add(gradeId);
      return next;
    });
  }

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

  const totalCols = students.length + 2;

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

          <div className="bg-white rounded-2xl border border-brand-border shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-white">
                    <th className="sticky left-0 z-30 bg-white px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted border-b border-brand-border min-w-[220px]">
                      Subtopic
                    </th>
                    {students.map((s) => {
                      const avg = studentOverallAvg(s.student_id);
                      return (
                        <th
                          key={s.student_id}
                          className="px-1.5 py-3 text-center border-b border-brand-border min-w-[80px]"
                        >
                          <div className="flex flex-col items-center gap-1.5">
                            <div className="[writing-mode:vertical-rl] rotate-180 text-xs font-semibold text-role-teacher-muted whitespace-nowrap">
                              {s.student_name}
                            </div>
                            <AvgBadge score={avg} />
                          </div>
                        </th>
                      );
                    })}
                    <th className="sticky right-0 z-30 bg-gray-50 px-3 py-3 text-center text-xs font-bold uppercase tracking-widest text-role-teacher-muted border-b border-l border-brand-border min-w-[90px]">
                      Class Avg
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {gradeGroups.map(({ gradeId, gradeName, topics }) => (
                    <>
                      <tr key={`grade-${gradeId}`}>
                        <td
                          colSpan={totalCols}
                          className="px-4 py-2 bg-brand-ink border-y border-brand-border cursor-pointer select-none"
                          onClick={() => toggleGrade(gradeId)}
                          aria-expanded={!collapsedGrades.has(gradeId)}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold uppercase tracking-widest text-white">
                              {gradeName}
                            </span>
                            {collapsedGrades.has(gradeId) ? (
                              <ChevronRight
                                className="w-4 h-4 text-white"
                                aria-hidden="true"
                              />
                            ) : (
                              <ChevronDown
                                className="w-4 h-4 text-white"
                                aria-hidden="true"
                              />
                            )}
                          </div>
                        </td>
                      </tr>
                      {!collapsedGrades.has(gradeId) &&
                        topics.map(({ topicId, topicName, nodes }) => {
                          const topicAvg = topicClassAvg(nodes);
                          return (
                            <>
                              <tr key={`topic-${gradeId}-${topicId}`}>
                                <td
                                  colSpan={totalCols}
                                  className="bg-brand-bg px-4 py-2 border-b border-brand-border"
                                >
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-semibold text-brand-ink">
                                      {topicName}
                                    </span>
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-xs text-brand-muted">
                                        topic avg
                                      </span>
                                      <AvgBadge score={topicAvg} />
                                    </div>
                                  </div>
                                </td>
                              </tr>
                              {nodes.map((node: any) => (
                                <tr
                                  key={node.subtopic_id}
                                  className="group hover:bg-amber-50/30 transition-colors"
                                >
                                  <td className="sticky left-0 z-10 bg-white group-hover:bg-amber-50/30 px-4 py-1.5 text-sm text-brand-ink border-b border-brand-border transition-colors">
                                    {node.subtopic_name}
                                  </td>
                                  {students.map((s) => {
                                    const ss = node.student_scores.find(
                                      (x: any) => x.student_id === s.student_id,
                                    );
                                    return (
                                      <td
                                        key={s.student_id}
                                        className="px-1.5 py-1.5 border-b border-brand-border"
                                      >
                                        <HeatCell
                                          score={ss?.mastery_score ?? null}
                                          label={`${s.student_name} — ${node.subtopic_name}`}
                                          onClick={() =>
                                            handleCellClick(
                                              s.student_id,
                                              s.student_name,
                                            )
                                          }
                                        />
                                      </td>
                                    );
                                  })}
                                  <td className="sticky right-0 z-10 bg-gray-50 px-1.5 py-1.5 border-b border-l border-brand-border">
                                    <HeatCell
                                      score={node.class_average}
                                      label={`Class average — ${node.subtopic_name}`}
                                      variant="summary"
                                    />
                                  </td>
                                </tr>
                              ))}
                            </>
                          );
                        })}
                    </>
                  ))}

                  <tr className="bg-brand-bg border-t-2 border-brand-border">
                    <td className="sticky left-0 z-10 bg-brand-bg px-4 py-3 text-xs font-bold uppercase tracking-widest text-role-teacher-muted">
                      Student Avg
                    </td>
                    {students.map((s) => (
                      <td
                        key={s.student_id}
                        className="px-1.5 py-3 text-center"
                      >
                        <AvgBadge score={studentOverallAvg(s.student_id)} />
                      </td>
                    ))}
                    <td className="sticky right-0 z-10 bg-brand-bg border-l border-brand-border" />
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
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
