import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Download } from "lucide-react";
import { useClassGapMap } from "../../hooks/useClassGapMap";
import { useClass } from "../../hooks/useClass";
import { GapMapCell } from "../../components/gap-map/GapMapCell";
import { LearningProfileSidePanel } from "../../components/gap-map/LearningProfileSidePanel";

export function GapMapPage() {
  const { classId } = useParams<{ classId: string }>();
  const { data: currentClass } = useClass(classId);
  const subjectId = currentClass?.subject_id ?? null;

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

  const { data, isLoading, isError } = useClassGapMap(
    classId ?? null,
    subjectId,
  );

  const firstNode = data?.nodes?.[0];
  const students = firstNode?.student_scores ?? [];

  const handleCellClick = (studentId: string, studentName: string) => {
    const subtopicScores =
      data?.nodes?.map((n: any) => {
        const studentScore = n.student_scores.find(
          (s: any) => s.student_id === studentId,
        );
        return {
          subtopicName: n.subtopic_name,
          topicName: n.topic_name,
          masteryScore: studentScore?.mastery_score ?? null,
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
    const csv = rows
      .map((r) => r.map((cell) => `"${cell}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const dateStr = new Date().toISOString().slice(0, 10);
    a.href = url;
    a.download = `gap-map-${(currentClass?.name ?? "class").replace(
      /\s+/g,
      "-",
    )}-${(currentClass?.subject_name ?? "subject").replace(/\s+/g, "-")}-${dateStr}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <nav
          className="flex items-center gap-2 text-sm text-brand-muted"
          aria-label="Breadcrumb"
        >
          <Link
            to="/teacher/classes"
            className="hover:text-brand-ink transition-colors"
          >
            Classes
          </Link>
          <span aria-hidden="true">/</span>
          <Link
            to={`/teacher/classes/${classId}`}
            className="hover:text-brand-ink transition-colors"
          >
            {currentClass?.name ?? "Class"}
          </Link>
          <span aria-hidden="true">/</span>
          <span className="text-brand-ink font-medium">Gap Map</span>
        </nav>
        {data && (
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

      <div>
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Gap Map
        </h1>
        <p className="text-sm text-brand-muted">
          {currentClass
            ? `${currentClass.name} — ${currentClass.subject_name}`
            : "Class mastery heatmap by subtopic"}
        </p>
      </div>

      {isError && (
        <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm">
          Failed to load gap map data. Please try again.
        </div>
      )}

      {isLoading && (
        <div className="animate-pulse space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-gray-100 rounded-lg" />
          ))}
        </div>
      )}

      {!isLoading && data && students.length === 0 && (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <span className="text-4xl mb-3" role="img" aria-label="chart">
            📊
          </span>
          <p className="font-display font-semibold text-brand-ink mb-2">
            No gap data yet
          </p>
          <p className="text-sm text-brand-muted mb-4">
            Run a Diagnostic assessment first — the Gap Map builds automatically
            from results. It shows exactly where each student has gaps against
            their curriculum topics.
          </p>
          <Link
            to="/teacher/assessments/new"
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold rounded transition-colors"
          >
            Create a Diagnostic →
          </Link>
        </div>
      )}

      {data && students.length > 0 && (
        <div className="bg-white rounded-2xl border border-brand-border shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-white z-10 px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-role-teacher-muted border-b border-brand-border min-w-[200px]">
                    Subtopic
                  </th>
                  {students.map((s: any) => (
                    <th
                      key={s.student_id}
                      className="px-2 py-3 text-center text-xs font-bold uppercase tracking-widest text-role-teacher-muted border-b border-brand-border min-w-[60px]"
                    >
                      <div className="[writing-mode:vertical-rl] rotate-180">
                        {s.student_name}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.nodes?.map((node: any) => (
                  <tr key={node.subtopic_id}>
                    <td className="sticky left-0 bg-white z-10 px-4 py-2 text-sm text-brand-ink border-b border-brand-border">
                      <div className="font-medium">{node.subtopic_name}</div>
                      <div className="text-xs text-brand-muted">
                        {node.topic_name}
                      </div>
                    </td>
                    {node.student_scores.map((ss: any) => (
                      <td
                        key={ss.student_id}
                        className="px-1 py-1 border-b border-brand-border"
                      >
                        <GapMapCell
                          masteryScore={ss.mastery_score}
                          studentId={ss.student_id}
                          studentName={ss.student_name}
                          subtopicName={node.subtopic_name}
                          onClick={() =>
                            handleCellClick(ss.student_id, ss.student_name)
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
                {/* Class average — pinned bottom row (spec requirement) */}
                <tr className="bg-brand-bg border-t-2 border-brand-border">
                  <td className="sticky left-0 bg-brand-bg z-10 px-4 py-2 text-xs font-bold uppercase tracking-widest text-role-teacher-muted border-b border-brand-border">
                    Class Avg
                  </td>
                  {data.nodes?.length > 0 &&
                    data.nodes[0].student_scores.map((ss: any) => {
                      const allScores = data.nodes
                        .map((n: any) => {
                          const s = n.student_scores.find(
                            (x: any) => x.student_id === ss.student_id,
                          );
                          return s?.mastery_score ?? null;
                        })
                        .filter((x: number | null): x is number => x !== null);
                      const avg =
                        allScores.length > 0
                          ? allScores.reduce(
                              (a: number, b: number) => a + b,
                              0,
                            ) / allScores.length
                          : null;
                      return (
                        <td
                          key={ss.student_id}
                          className="px-1 py-1 border-b border-brand-border text-center"
                        >
                          <span className="text-xs font-semibold text-brand-ink">
                            {avg !== null ? `${Math.round(avg * 100)}%` : "—"}
                          </span>
                        </td>
                      );
                    })}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data && students.length > 0 && (
        <p className="text-sm text-brand-muted mt-4">
          Click any cell to view that student&apos;s learning profile and assign
          a targeted study plan directly.
        </p>
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
