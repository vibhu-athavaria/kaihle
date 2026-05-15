import { getMasteryStyle } from "@kaihle/types";
import { useStudentMiniCourseProgress } from "../../hooks/useStudentMiniCourseProgress";

interface MiniCoursesTabProps {
  studentId: string;
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="text-brand-muted">—</span>;
  }
  const { textClass, bgClass, label } = getMasteryStyle(score);
  const pct = Math.round(score * 100);
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${textClass} ${bgClass}`}
      aria-label={`${pct}% — ${label}`}
    >
      {pct}%
    </span>
  );
}

function AccessedCell({ accessed }: { accessed: boolean }) {
  if (accessed) {
    return (
      <span className="text-brand-green font-semibold" aria-label="Accessed">
        ✓
      </span>
    );
  }
  return (
    <span className="text-brand-muted" aria-label="Not accessed">
      —
    </span>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 4 }).map((_, i) => (
        <tr key={i} className="border-b border-brand-border">
          {Array.from({ length: 6 }).map((__, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 bg-gray-100 rounded animate-pulse w-full" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function MiniCoursesTab({ studentId }: MiniCoursesTabProps) {
  const { data, isLoading, isError } = useStudentMiniCourseProgress(studentId);

  if (isError) {
    return (
      <div className="text-red-600 p-4 bg-red-50 rounded-lg text-sm">
        Failed to load mini-course progress. Please try again.
      </div>
    );
  }

  const progress = data?.progress ?? [];

  return (
    <div className="space-y-4">
      <h2 className="font-display font-bold text-lg text-brand-ink">
        Mini-Course Progress
      </h2>

      {!isLoading && progress.length === 0 ? (
        <div className="text-center py-16 px-6">
          <div className="text-4xl mb-4">📚</div>
          <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
            No mini-courses started yet
          </h3>
          <p className="text-brand-body text-sm max-w-sm mx-auto">
            This student hasn&apos;t visited any mini-course content yet.
            Mini-courses appear here once they start exploring subtopics.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-brand-border">
          <table className="w-full text-sm font-sans">
            <thead>
              <tr className="bg-gray-50 border-b border-brand-border text-left">
                <th className="px-4 py-3 font-semibold text-brand-ink">
                  Subtopic
                </th>
                <th className="px-4 py-3 font-semibold text-brand-ink">
                  Topic
                </th>
                <th className="px-4 py-3 font-semibold text-brand-ink">
                  Last Visited
                </th>
                <th className="px-4 py-3 font-semibold text-brand-ink text-center">
                  Explanation
                </th>
                <th className="px-4 py-3 font-semibold text-brand-ink text-center">
                  Video
                </th>
                <th className="px-4 py-3 font-semibold text-brand-ink text-center">
                  Score
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <SkeletonRows />
              ) : (
                progress.map((item) => (
                  <tr
                    key={item.subtopic_id}
                    className="border-b border-brand-border last:border-0 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 text-brand-ink font-medium">
                      {item.subtopic_name}
                    </td>
                    <td className="px-4 py-3 text-brand-body">
                      {item.topic_name}
                    </td>
                    <td className="px-4 py-3 text-brand-body">
                      {new Date(item.last_visited_at).toLocaleDateString(
                        undefined,
                        { year: "numeric", month: "short", day: "numeric" },
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <AccessedCell accessed={item.explanation_accessed} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <AccessedCell accessed={item.video_accessed} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ScoreBadge score={item.check_questions_score} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
