import { useNavigate } from "react-router-dom";
import { Target, CheckCircle, Circle, Loader } from "lucide-react";
import { useMyStudyPlans } from "../../../hooks/useMyStudyPlans";

interface StudyPlanTabProps {
  classId: string;
  diagnosticStatus: "PENDING" | "IN_PROGRESS" | "COMPLETED";
}

export function StudyPlanTab({ classId, diagnosticStatus }: StudyPlanTabProps) {
  const navigate = useNavigate();

  // Only fetch when diagnostic is completed
  const { data: plansPage, isPending, isError } = useMyStudyPlans();

  if (diagnosticStatus === "PENDING" || diagnosticStatus === "IN_PROGRESS") {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 flex flex-col items-center text-center gap-4">
        <div className="text-4xl">🎯</div>
        <div>
          <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
            Complete your diagnostic first
          </h3>
          <p className="font-sans text-sm text-brand-body max-w-sm mx-auto">
            Your personalised study plan is generated after you complete the
            class diagnostic. It only takes a few minutes!
          </p>
        </div>
        <button
          onClick={() => navigate("/student/assessments")}
          className="bg-brand-primary text-white rounded-full px-6 py-2.5 font-sans font-semibold text-sm hover:bg-brand-primary/90 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 transition-colors"
        >
          Go to Assessments
        </button>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-16 px-6">
        <p className="font-sans text-sm text-brand-body">
          Something went wrong loading your study plan. Please refresh the page.
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
            className="h-16 bg-brand-border rounded-xl animate-pulse"
          />
        ))}
      </div>
    );
  }

  // Filter plans for this class
  const classPlans = (plansPage?.data ?? []).filter(
    (p) => p.class_id === classId,
  );

  if (classPlans.length === 0) {
    return (
      <div className="text-center py-16 px-6">
        <div className="text-4xl mb-4">📋</div>
        <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
          No study plan yet
        </h3>
        <p className="font-sans text-brand-body text-sm max-w-sm mx-auto">
          Your study plan will appear here once it&apos;s generated after your
          diagnostic.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {classPlans.map((plan) => {
        const isGenerating = plan.status === "GENERATING";
        const isCompleted = plan.status === "COMPLETED";

        return (
          <button
            key={plan.id}
            onClick={() =>
              !isGenerating
                ? navigate(`/student/study-plans/${plan.id}`)
                : undefined
            }
            disabled={isGenerating}
            className="w-full text-left bg-white rounded-xl border border-brand-border p-4 shadow-sm transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-default disabled:hover:shadow-sm"
          >
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0">
                {isGenerating ? (
                  <Loader
                    className="w-5 h-5 text-brand-muted animate-spin"
                    aria-hidden="true"
                  />
                ) : isCompleted ? (
                  <CheckCircle
                    className="w-5 h-5 text-brand-green"
                    aria-hidden="true"
                  />
                ) : (
                  <Circle
                    className="w-5 h-5 text-brand-amber"
                    aria-hidden="true"
                  />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-sans font-semibold text-base text-brand-ink truncate">
                  {plan.subtopic_name}
                </h3>
                <p className="font-sans text-sm text-brand-body">
                  {isGenerating ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="inline-block w-2 h-2 rounded-full bg-brand-amber animate-pulse" />
                      Generating…
                    </span>
                  ) : (
                    `${plan.resources.length} resource${plan.resources.length !== 1 ? "s" : ""} · ${plan.status.charAt(0) + plan.status.slice(1).toLowerCase()}`
                  )}
                </p>
              </div>
              {!isGenerating && (
                <Target
                  className="w-4 h-4 text-brand-muted flex-shrink-0"
                  aria-hidden="true"
                />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
