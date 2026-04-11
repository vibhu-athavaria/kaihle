import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
import type { StudentGapMap } from "../../hooks/useStudentProfile";

interface GapProfileSectionProps {
  gapMap: StudentGapMap | null;
}

export function GapProfileSection({ gapMap }: GapProfileSectionProps) {
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());

  if (!gapMap || !gapMap.scores || gapMap.scores.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-brand-border shadow-sm p-6">
        <h2 className="font-display font-semibold text-lg text-brand-ink mb-4">
          Gap Profile
        </h2>
        <p className="text-sm text-brand-muted italic">
          No gap profile data available.
        </p>
      </div>
    );
  }

  const topicGroups = gapMap.scores.reduce(
    (acc, score) => {
      const key = score.topic_id;
      if (!acc[key]) {
        acc[key] = {
          topicId: score.topic_id,
          topicName: score.topic_name,
          subtopics: [],
        };
      }
      acc[key].subtopics.push(score);
      return acc;
    },
    {} as Record<
      string,
      { topicId: string; topicName: string; subtopics: typeof gapMap.scores }
    >,
  );

  const toggleTopic = (topicId: string) => {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicId)) {
        next.delete(topicId);
      } else {
        next.add(topicId);
      }
      return next;
    });
  };

  const allTopics = Object.values(topicGroups);

  return (
    <div className="bg-white rounded-2xl border border-brand-border shadow-sm p-5">
      <h2 className="font-display font-semibold text-lg text-brand-ink mb-4">
        Gap Profile
      </h2>
      <div className="space-y-2">
        {allTopics.map((topic) => {
          const isExpanded = expandedTopics.has(topic.topicId);

          return (
            <div
              key={topic.topicId}
              className="border border-brand-border rounded-lg overflow-hidden"
            >
              <button
                type="button"
                onClick={() => toggleTopic(topic.topicId)}
                className="w-full flex items-center justify-between px-4 py-3 bg-brand-bg hover:bg-gray-100 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-brand-muted" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-brand-muted" />
                  )}
                  <span className="font-medium text-brand-ink">
                    {topic.topicName}
                  </span>
                </div>
                <span className="text-sm text-brand-muted">
                  {topic.subtopics.length} subtopic
                  {topic.subtopics.length !== 1 ? "s" : ""}
                </span>
              </button>
              {isExpanded && (
                <div className="divide-y divide-brand-border">
                  {topic.subtopics.map((subtopic) => {
                    const { textClass, bgClass, label } = getMasteryStyle(
                      subtopic.mastery_score,
                    );
                    const displayPct = scoreToPercent(subtopic.mastery_score);

                    return (
                      <div
                        key={subtopic.subtopic_id}
                        className={`flex items-center justify-between px-4 py-3 ${bgClass}`}
                      >
                        <div>
                          <div className="text-sm font-medium text-brand-ink">
                            {subtopic.subtopic_name}
                          </div>
                          {subtopic.last_assessed_at && (
                            <div className="text-xs text-brand-muted mt-0.5">
                              Assessed:{" "}
                              {new Date(
                                subtopic.last_assessed_at,
                              ).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                        <div className="text-right">
                          <div className={`text-sm font-semibold ${textClass}`}>
                            {displayPct}
                          </div>
                          <div className="text-xs text-brand-muted">
                            {label}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
