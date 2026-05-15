import { useNavigate } from "react-router-dom";
import { ArrowRight, Package } from "lucide-react";
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
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-32 bg-brand-border rounded-xl animate-pulse"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {lessonPackReady && (
        <div className="flex items-center gap-3 bg-brand-green-light border border-brand-green rounded-xl p-4">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {topics.map((topic) => (
            <button
              key={topic.id}
              onClick={() =>
                navigate(`/student/classes/${classId}/topics/${topic.id}`)
              }
              className="group text-left bg-white rounded-xl border border-brand-border p-5 shadow-sm transition-all hover:border-brand-primary hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              <div className="flex flex-col h-full gap-3">
                <div className="flex-1 min-w-0">
                  <h3 className="font-sans font-semibold text-base text-brand-ink leading-snug">
                    {topic.name}
                  </h3>
                  {topic.description && (
                    <p className="font-sans text-sm text-brand-body mt-1 line-clamp-2">
                      {topic.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 text-xs font-semibold text-brand-primary group-hover:gap-2 transition-all">
                  Learn
                  <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                </div>
              </div>
            </button>
          ))}
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
