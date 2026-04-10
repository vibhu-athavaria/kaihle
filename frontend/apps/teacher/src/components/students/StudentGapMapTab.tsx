import { getMasteryStyle } from "@kaihle/types";

interface Score {
  subtopic_id: string;
  subtopic_name: string;
  topic_id: string;
  topic_name: string;
  mastery_score: number | null;
  last_assessed_at: string | null;
}

interface StudentGapMapTabProps {
  scores: Score[];
  classId?: string;
}

export function StudentGapMapTab({ scores, classId }: StudentGapMapTabProps) {
  const topicMap = new Map<string, { topicName: string; scores: Score[] }>();
  for (const score of scores) {
    if (!topicMap.has(score.topic_id)) {
      topicMap.set(score.topic_id, { topicName: score.topic_name, scores: [] });
    }
    topicMap.get(score.topic_id)!.scores.push(score);
  }

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-100 text-blue-700 text-xs p-3 rounded-xl flex items-center justify-between">
        <span>
          This view shows this student's gaps. To assign a study plan, use the
          class Gap Map and select this student's cell.
        </span>
        {classId && (
          <a
            href={`/teacher/classes/${classId}/gap-map`}
            className="ml-3 font-bold underline whitespace-nowrap"
          >
            Go to Gap Map →
          </a>
        )}
      </div>

      {scores.length === 0 ? (
        <div className="text-center py-12 text-brand-muted text-sm">
          No gap map data yet. The student will appear here after completing
          assessments.
        </div>
      ) : (
        Array.from(topicMap.entries()).map(
          ([topicId, { topicName, scores: topicScores }]) => (
            <div
              key={topicId}
              className="bg-white rounded-xl border border-brand-border overflow-hidden"
            >
              <div className="px-4 py-3 bg-brand-bg border-b border-brand-border">
                <span className="font-display font-semibold text-sm text-brand-ink uppercase tracking-wide">
                  {topicName}
                </span>
              </div>
              <div className="divide-y divide-brand-border">
                {topicScores.map((score) => {
                  const { textClass } = getMasteryStyle(score.mastery_score);
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
                            ? `Last assessed ${new Date(
                                score.last_assessed_at,
                              ).toLocaleDateString("en-GB")}`
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
            </div>
          ),
        )
      )}
    </div>
  );
}
