import { useNavigate } from "react-router-dom";
import { Package } from "lucide-react";
import { getMasteryStyle } from "@kaihle/types";
import { useClassTopics } from "../../../hooks/useClassTopics";

interface TopicsTabProps {
  classId: string;
  lessonPackReady?: boolean;
}

export function TopicsTab({ classId, lessonPackReady }: TopicsTabProps) {
  const navigate = useNavigate();
  const { data: topics, isPending, isError } = useClassTopics(classId);

  if (isError) {
    return (
      <div className="text-center py-16 px-6">
        <p className="font-sans text-sm text-brand-body">
          Something went wrong loading topics. Please refresh the page.
        </p>
      </div>
    );
  }

  if (isPending) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 bg-brand-border rounded-card animate-pulse"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {lessonPackReady && (
        <div className="flex items-center gap-3 bg-brand-green-light border border-brand-green rounded-card p-4">
          <Package
            className="w-5 h-5 text-brand-green flex-shrink-0"
            aria-hidden="true"
          />
          <p className="font-sans text-sm text-brand-green font-semibold">
            Your lesson pack is ready — explore personalised resources below
            each topic.
          </p>
        </div>
      )}

      {topics && topics.length > 0 ? (
        <div className="space-y-3">
          {topics.map((topic) => {
            // Topic type doesn't carry mastery score — show neutral state
            const masteryScore: number | null = null;
            const { dotClass, label } = getMasteryStyle(masteryScore);

            return (
              <button
                key={topic.id}
                onClick={() =>
                  navigate(`/student/classes/${classId}/topics/${topic.id}`)
                }
                className="w-full text-left bg-white rounded-card border border-brand-border p-4 shadow-sm transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-5 h-5 rounded-full flex-shrink-0 ${dotClass}`}
                    aria-label={label}
                    role="img"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-sans font-semibold text-base text-brand-ink truncate">
                      {topic.name}
                    </h3>
                    {topic.description && (
                      <p className="font-sans text-sm text-brand-body truncate">
                        {topic.description}
                      </p>
                    )}
                  </div>
                  <div className="flex-shrink-0 w-24">
                    <div className="w-full bg-brand-border rounded-full h-2">
                      <div
                        className="bg-brand-muted h-2 rounded-full"
                        style={{ width: "0%" }}
                        role="progressbar"
                        aria-valuenow={0}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${topic.name} progress: not assessed`}
                      />
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-16 px-6">
          <div className="text-4xl mb-4">📚</div>
          <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
            No topics yet
          </h3>
          <p className="font-sans text-brand-body text-sm max-w-sm mx-auto">
            Your teacher will add topics to this class soon.
          </p>
        </div>
      )}
    </div>
  );
}
