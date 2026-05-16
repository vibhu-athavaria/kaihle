import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

// ── Public types ─────────────────────────────────────────────────────────────

export interface GapMapStudentScore {
  student_id: string;
  student_name: string;
  mastery_score: number | null;
}

export interface GapMapNode {
  subtopic_id: string;
  subtopic_name: string;
  topic_id: string;
  topic_name: string;
  grade_id: string;
  grade_name: string;
  grade_level: number;
  class_average: number | null;
  student_count: number;
  student_scores: GapMapStudentScore[];
}

export interface ClassGapMapTableProps {
  nodes: GapMapNode[];
  variant: "teacher" | "school-admin";
  /**
   * Called when a student cell is clicked. Teacher app opens the learning-profile
   * side panel. School-admin omits this prop (read-only).
   */
  onCellClick?: (studentId: string, studentName: string) => void;
}

// ── Variant palette config ────────────────────────────────────────────────────

const VARIANT_CONFIG = {
  teacher: {
    gradeHeaderBg: "bg-brand-ink",
    gradeHeaderText: "text-white",
    topicRowBg: "bg-brand-bg",
    borderColor: "border-brand-border",
    hoverRow: "hover:bg-amber-50/30",
    stickyLeftBg: "bg-white",
    stickyLeftHover: "group-hover:bg-amber-50/30",
  },
  "school-admin": {
    gradeHeaderBg: "bg-brand-primary",
    gradeHeaderText: "text-white",
    topicRowBg: "bg-brand-surface-subtle",
    borderColor: "border-role-school-border",
    hoverRow: "hover:bg-gray-50/50",
    stickyLeftBg: "bg-white",
    stickyLeftHover: "",
  },
} as const;

// ── Internal sub-components ───────────────────────────────────────────────────

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

function HeatCell({
  score,
  label,
  onClick,
  variant = "summary",
}: {
  score: number | null;
  label: string;
  onClick?: () => void;
  variant?: "default" | "summary";
}) {
  const { bgClass, textClass, label: masteryLabel } = getMasteryStyle(score);
  const pct = scoreToPercent(score);

  const baseClass = [
    "w-full h-12 flex flex-col items-center justify-center gap-0.5 rounded select-none",
    bgClass,
    textClass,
    variant === "summary" ? "ring-1 ring-inset ring-black/10" : "",
  ].join(" ");

  const content =
    score !== null ? (
      <>
        <span className="text-xs font-bold leading-none">{pct}</span>
        <span className="text-[10px] font-medium leading-none opacity-70">
          {masteryLabel}
        </span>
      </>
    ) : (
      <span className="text-xs font-medium opacity-40">—</span>
    );

  if (!onClick) {
    return (
      <div className={baseClass} aria-label={label}>
        {content}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={[
        baseClass,
        "transition-all hover:scale-[1.06] hover:shadow-lg hover:z-10 relative",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1",
      ].join(" ")}
    >
      {content}
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ClassGapMapTable({
  nodes,
  variant,
  onCellClick,
}: ClassGapMapTableProps) {
  const cfg = VARIANT_CONFIG[variant];

  // ── Build grade → topic → node tree ──────────────────────────────────────

  type TopicGroup = { topicId: string; topicName: string; nodes: GapMapNode[] };
  type GradeGroup = {
    gradeId: string;
    gradeName: string;
    topics: TopicGroup[];
  };

  const gradeGroups: GradeGroup[] = [];
  const gradeIndexMap = new Map<string, number>();
  const topicIndexMap = new Map<string, number>();

  nodes.forEach((n) => {
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

  // ── Derive unique student list ────────────────────────────────────────────

  const studentMap = new Map<string, string>();
  nodes.forEach((n) =>
    n.student_scores.forEach((s) =>
      studentMap.set(s.student_id, s.student_name),
    ),
  );
  const students = Array.from(studentMap.entries()).map(([id, name]) => ({
    id,
    name,
  }));

  // ── Collapse state: topics with mastery data start open ───────────────────

  const emptyTopicKeys = new Set(
    gradeGroups.flatMap((g) =>
      g.topics
        .filter((t) => t.nodes.every((n) => n.class_average === null))
        .map((t) => `${g.gradeId}:${t.topicId}`),
    ),
  );

  const [collapsedGrades, setCollapsedGrades] = useState<Set<string>>(
    new Set(),
  );
  const [collapsedTopics, setCollapsedTopics] = useState<Set<string>>(
    () => new Set(emptyTopicKeys),
  );

  function toggleGrade(gradeId: string) {
    setCollapsedGrades((prev) => {
      const next = new Set(prev);
      if (next.has(gradeId)) next.delete(gradeId);
      else next.add(gradeId);
      return next;
    });
  }

  function toggleTopic(topicKey: string) {
    setCollapsedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicKey)) next.delete(topicKey);
      else next.add(topicKey);
      return next;
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function topicClassAvg(topicNodes: GapMapNode[]): number | null {
    const avgs = topicNodes
      .map((n) => n.class_average)
      .filter((x): x is number => x !== null);
    return avgs.length > 0
      ? avgs.reduce((a, b) => a + b, 0) / avgs.length
      : null;
  }

  function studentOverallAvg(studentId: string): number | null {
    const scores = nodes
      .map(
        (n) =>
          n.student_scores.find((s) => s.student_id === studentId)
            ?.mastery_score ?? null,
      )
      .filter((x): x is number => x !== null);
    return scores.length > 0
      ? scores.reduce((a, b) => a + b, 0) / scores.length
      : null;
  }

  const totalCols = students.length + 2;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div
      className={`bg-white rounded-2xl border ${cfg.borderColor} shadow-sm overflow-hidden`}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-white">
              <th
                className={`sticky left-0 z-30 bg-white px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-brand-muted border-b ${cfg.borderColor} min-w-[220px]`}
              >
                Subtopic
              </th>
              {students.map((s) => (
                <th
                  key={s.id}
                  className={`px-1.5 py-3 text-center border-b ${cfg.borderColor} min-w-[80px]`}
                >
                  <div className="flex flex-col items-center gap-1.5">
                    <div className="[writing-mode:vertical-rl] rotate-180 text-xs font-semibold text-brand-muted whitespace-nowrap">
                      {s.name}
                    </div>
                    {variant === "teacher" && (
                      <AvgBadge score={studentOverallAvg(s.id)} />
                    )}
                  </div>
                </th>
              ))}
              <th
                className={`sticky right-0 z-30 bg-gray-50 px-3 py-3 text-center text-xs font-bold uppercase tracking-widest text-brand-muted border-b border-l ${cfg.borderColor} min-w-[90px]`}
              >
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
                    className={`px-4 py-2 ${cfg.gradeHeaderBg} border-y ${cfg.borderColor} cursor-pointer select-none`}
                    onClick={() => toggleGrade(gradeId)}
                    aria-expanded={!collapsedGrades.has(gradeId)}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-xs font-bold uppercase tracking-widest ${cfg.gradeHeaderText}`}
                      >
                        {gradeName}
                      </span>
                      {collapsedGrades.has(gradeId) ? (
                        <ChevronRight
                          className={`w-4 h-4 ${cfg.gradeHeaderText}`}
                          aria-hidden="true"
                        />
                      ) : (
                        <ChevronDown
                          className={`w-4 h-4 ${cfg.gradeHeaderText}`}
                          aria-hidden="true"
                        />
                      )}
                    </div>
                  </td>
                </tr>

                {!collapsedGrades.has(gradeId) &&
                  topics.map(({ topicId, topicName, nodes: topicNodes }) => {
                    const topicKey = `${gradeId}:${topicId}`;
                    const isTopicCollapsed = collapsedTopics.has(topicKey);
                    const topicAvg = topicClassAvg(topicNodes);

                    return (
                      <>
                        <tr key={`topic-${topicKey}`}>
                          <td
                            colSpan={totalCols}
                            className={`${cfg.topicRowBg} px-4 py-2 border-b ${cfg.borderColor} cursor-pointer select-none`}
                            onClick={() => toggleTopic(topicKey)}
                            aria-expanded={!isTopicCollapsed}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1.5">
                                {isTopicCollapsed ? (
                                  <ChevronRight
                                    className="w-3.5 h-3.5 text-brand-muted"
                                    aria-hidden="true"
                                  />
                                ) : (
                                  <ChevronDown
                                    className="w-3.5 h-3.5 text-brand-muted"
                                    aria-hidden="true"
                                  />
                                )}
                                <span className="text-xs font-semibold text-brand-ink">
                                  {topicName}
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs text-brand-muted">
                                  topic avg
                                </span>
                                <AvgBadge score={topicAvg} />
                              </div>
                            </div>
                          </td>
                        </tr>

                        {!isTopicCollapsed &&
                          topicNodes.map((node) => (
                            <tr
                              key={node.subtopic_id}
                              className={`group ${cfg.hoverRow} transition-colors`}
                            >
                              <td
                                className={`sticky left-0 z-10 ${cfg.stickyLeftBg} ${cfg.stickyLeftHover} px-4 py-1.5 text-sm text-brand-ink border-b ${cfg.borderColor} transition-colors`}
                              >
                                {node.subtopic_name}
                              </td>
                              {students.map((s) => {
                                const ss = node.student_scores.find(
                                  (x) => x.student_id === s.id,
                                );
                                return (
                                  <td
                                    key={s.id}
                                    className={`px-1.5 py-1.5 border-b ${cfg.borderColor}`}
                                  >
                                    <HeatCell
                                      score={ss?.mastery_score ?? null}
                                      label={`${s.name} — ${node.subtopic_name}`}
                                      onClick={
                                        onCellClick
                                          ? () => onCellClick(s.id, s.name)
                                          : undefined
                                      }
                                    />
                                  </td>
                                );
                              })}
                              <td
                                className={`sticky right-0 z-10 bg-gray-50 px-1.5 py-1.5 border-b border-l ${cfg.borderColor}`}
                              >
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

            {/* Student average footer row — teacher only */}
            {variant === "teacher" && (
              <tr className={`bg-brand-bg border-t-2 ${cfg.borderColor}`}>
                <td className="sticky left-0 z-10 bg-brand-bg px-4 py-3 text-xs font-bold uppercase tracking-widest text-brand-muted">
                  Student Avg
                </td>
                {students.map((s) => (
                  <td key={s.id} className="px-1.5 py-3 text-center">
                    <AvgBadge score={studentOverallAvg(s.id)} />
                  </td>
                ))}
                <td
                  className={`sticky right-0 z-10 bg-brand-bg border-l ${cfg.borderColor}`}
                />
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
