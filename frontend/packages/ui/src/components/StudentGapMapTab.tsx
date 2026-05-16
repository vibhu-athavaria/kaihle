import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { getMasteryStyle } from "@kaihle/types";

export interface StudentSubtopicScore {
  subtopic_id: string;
  subtopic_name: string;
  topic_id: string;
  topic_name: string;
  mastery_score: number | null;
  last_assessed_at: string | null;
}

export interface StudentGapMapTabProps {
  scores: StudentSubtopicScore[];
  /** Renders an info banner with a link back to the class gap map. Teacher-only. */
  classGapMapHref?: string;
}

export function StudentGapMapTab({
  scores,
  classGapMapHref,
}: StudentGapMapTabProps) {
  const topicMap = new Map<
    string,
    { topicName: string; scores: StudentSubtopicScore[] }
  >();
  for (const score of scores) {
    if (!topicMap.has(score.topic_id)) {
      topicMap.set(score.topic_id, { topicName: score.topic_name, scores: [] });
    }
    topicMap.get(score.topic_id)!.scores.push(score);
  }

  // Topics with any assessed subtopic default open; fully unassessed topics default closed.
  const emptyTopicIds = new Set(
    Array.from(topicMap.entries())
      .filter(([, { scores: s }]) => s.every((x) => x.mastery_score === null))
      .map(([id]) => id),
  );

  const [collapsedTopics, setCollapsedTopics] = useState<Set<string>>(
    () => new Set(emptyTopicIds),
  );

  function toggleTopic(topicId: string) {
    setCollapsedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicId)) next.delete(topicId);
      else next.add(topicId);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {classGapMapHref && (
        <div className="bg-blue-50 border border-blue-100 text-blue-700 text-xs p-3 rounded-xl flex items-center justify-between">
          <span>
            This view shows this student&apos;s gaps. To assign a study plan,
            use the class Gap Map and select this student&apos;s cell.
          </span>
          <a
            href={classGapMapHref}
            className="ml-3 font-bold text-brand-gold hover:text-brand-gold-dark underline whitespace-nowrap"
          >
            Go to Gap Map →
          </a>
        </div>
      )}

      {scores.length === 0 ? (
        <div className="text-center py-12 text-brand-muted text-sm">
          No gap map data yet. The student will appear here after completing
          assessments.
        </div>
      ) : (
        Array.from(topicMap.entries()).map(
          ([topicId, { topicName, scores: topicScores }]) => {
            const isCollapsed = collapsedTopics.has(topicId);
            return (
              <div
                key={topicId}
                className="bg-white rounded-xl border border-brand-border overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => toggleTopic(topicId)}
                  aria-expanded={!isCollapsed}
                  className="w-full flex items-center justify-between px-4 py-3 bg-brand-bg border-b border-brand-border text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-inset"
                >
                  <span className="font-display font-semibold text-sm text-brand-ink uppercase tracking-wide">
                    {topicName}
                  </span>
                  {isCollapsed ? (
                    <ChevronRight
                      className="w-4 h-4 text-brand-muted flex-shrink-0"
                      aria-hidden="true"
                    />
                  ) : (
                    <ChevronDown
                      className="w-4 h-4 text-brand-muted flex-shrink-0"
                      aria-hidden="true"
                    />
                  )}
                </button>

                {!isCollapsed && (
                  <div className="divide-y divide-brand-border">
                    {topicScores.map((score) => {
                      const { textClass } = getMasteryStyle(
                        score.mastery_score,
                      );
                      return (
                        <div
                          key={score.subtopic_id}
                          className="flex items-center justify-between px-4 py-3"
                        >
                          <div>
                            <div className="text-sm font-medium text-brand-ink">
                              {score.subtopic_name}
                            </div>
                            <div className="text-xs text-brand-muted">
                              {score.last_assessed_at
                                ? `Last assessed ${new Date(score.last_assessed_at).toLocaleDateString("en-GB")}`
                                : "Not yet assessed"}
                            </div>
                          </div>
                          <div className={`text-sm font-semibold ${textClass}`}>
                            {score.mastery_score !== null
                              ? `${Math.round(score.mastery_score * 100)}%`
                              : "—"}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          },
        )
      )}
    </div>
  );
}
