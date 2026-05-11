import { getMasteryStyle } from "@kaihle/types";
import { useStudentGapMap } from "../../../hooks/useStudentGapMap";

interface MyProgressTabProps {
  subjectId: string;
}

export function MyProgressTab({ subjectId }: MyProgressTabProps) {
  const { data: gapMap, isPending, isError } = useStudentGapMap(subjectId);

  if (isError) {
    return (
      <div className="text-center py-16 px-6">
        <p className="font-sans text-sm text-brand-body">
          Something went wrong loading your progress. Please refresh the page.
        </p>
      </div>
    );
  }

  if (isPending) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-14 bg-brand-border rounded-card animate-pulse"
          />
        ))}
      </div>
    );
  }

  const scores = gapMap?.scores ?? [];

  if (scores.length === 0) {
    return (
      <div role="status" className="text-center py-12">
        <p className="text-sm font-semibold text-brand-body">
          No progress data yet.
        </p>
        <p className="text-xs text-brand-muted mt-1">
          Complete your first assessment to see your progress here.
        </p>
      </div>
    );
  }

  // Group by topic
  const byTopic = scores.reduce<
    Record<string, { topicName: string; subtopics: typeof scores }>
  >((acc, s) => {
    if (!acc[s.topic_id]) {
      acc[s.topic_id] = { topicName: s.topic_name, subtopics: [] };
    }
    acc[s.topic_id].subtopics.push(s);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(byTopic).map(([topicId, { topicName, subtopics }]) => (
        <div key={topicId}>
          <h3 className="font-sans text-xs font-bold uppercase tracking-[0.8px] text-brand-muted mb-3">
            {topicName}
          </h3>
          <div className="space-y-2">
            {subtopics.map((s) => {
              const { dotClass, label, textClass } = getMasteryStyle(
                s.mastery_score,
              );
              const pct =
                s.mastery_score !== null
                  ? Math.round(s.mastery_score * 100)
                  : 0;

              return (
                <div
                  key={s.subtopic_id}
                  className="flex items-center gap-3 bg-white rounded-card border border-brand-border px-4 py-3"
                >
                  <span
                    className={`w-5 h-5 rounded-full flex-shrink-0 ${dotClass}`}
                    aria-label={label}
                    role="img"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="font-sans text-sm font-medium text-brand-ink truncate">
                      {s.subtopic_name}
                    </p>
                    {s.mastery_score === null && (
                      <p className="font-sans text-xs text-brand-muted italic">
                        Not assessed
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="w-20">
                      <div className="w-full bg-brand-border rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-500 ${s.mastery_score !== null ? dotClass : "bg-brand-muted"}`}
                          style={{ width: `${pct}%` }}
                          role="progressbar"
                          aria-valuenow={pct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${s.subtopic_name}: ${label}, ${pct}%`}
                        />
                      </div>
                    </div>
                    {s.mastery_score !== null && (
                      <span
                        className={`font-sans text-xs font-semibold w-8 text-right ${textClass}`}
                      >
                        {pct}%
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
