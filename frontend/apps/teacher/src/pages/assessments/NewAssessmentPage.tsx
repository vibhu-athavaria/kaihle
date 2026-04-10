import { useEffect } from "react";
import { useAssessmentWizard } from "../../hooks/useAssessmentWizard";
import { Step1ClassAndType } from "./steps/Step1ClassAndType";
import { Step2Topics } from "./steps/Step2Topics";
import { Step3Configure } from "./steps/Step3Configure";
import { Step4Preview } from "./steps/Step4Preview";
import { Step5Publish } from "./steps/Step5Publish";

const STEPS = [
  { number: 1, label: "Class & Type" },
  { number: 2, label: "Topics" },
  { number: 3, label: "Configure" },
  { number: 4, label: "Preview" },
  { number: 5, label: "Publish" },
] as const;

type StepNumber = (typeof STEPS)[number]["number"];

function StepIndicator({
  steps,
  currentStep,
  skipsStep2,
}: {
  steps: typeof STEPS;
  currentStep: StepNumber;
  skipsStep2: boolean;
}) {
  return (
    <nav aria-label="Assessment creation steps" className="mb-8">
      <ol className="flex items-center gap-0">
        {steps.map((step, idx) => {
          const isSkipped = skipsStep2 && step.number === 2;
          const isActive = step.number === currentStep;
          const isCompleted = step.number < currentStep && !isSkipped;

          return (
            <li key={step.number} className="flex items-center flex-1">
              {idx > 0 && (
                <div
                  className={[
                    "h-px flex-1 mx-2",
                    isCompleted || (isSkipped && step.number < currentStep)
                      ? "bg-brand-gold"
                      : "bg-brand-border",
                  ].join(" ")}
                  aria-hidden="true"
                />
              )}
              <div className="flex flex-col items-center">
                <span
                  className={[
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold font-sans transition-colors",
                    isActive
                      ? "bg-brand-gold text-white"
                      : isCompleted
                        ? "bg-brand-gold-light text-brand-gold-dark border border-brand-gold-mid"
                        : isSkipped
                          ? "bg-brand-border-soft text-brand-muted border border-brand-border"
                          : "bg-white text-brand-muted border border-brand-border",
                  ].join(" ")}
                  aria-current={isActive ? "step" : undefined}
                >
                  {step.number}
                </span>
                <span
                  className={[
                    "mt-1 text-[10px] font-sans hidden sm:block",
                    isActive
                      ? "text-brand-gold-dark font-bold"
                      : isSkipped
                        ? "text-brand-muted line-through"
                        : "text-brand-muted",
                  ].join(" ")}
                >
                  {step.label}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function renderStep(step: StepNumber) {
  switch (step) {
    case 1:
      return <Step1ClassAndType />;
    case 2:
      return <Step2Topics />;
    case 3:
      return <Step3Configure />;
    case 4:
      return <Step4Preview />;
    case 5:
      return <Step5Publish />;
  }
}

export function NewAssessmentPage() {
  const { currentStep, assessmentType, reset } = useAssessmentWizard();

  // Reset wizard on unmount so stale state doesn't persist
  useEffect(() => {
    return () => {
      reset();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const skipsStep2 =
    assessmentType === "DIAGNOSTIC" || assessmentType === "FINAL";

  const stepTitles: Record<StepNumber, string> = {
    1: "Choose Class & Type",
    2: "Select Topics",
    3: "Configure Assessment",
    4: "Preview Questions",
    5: "Review & Publish",
  };

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
          New Assessment
        </h1>

        <StepIndicator
          steps={STEPS}
          currentStep={currentStep}
          skipsStep2={skipsStep2}
        />

        <div className="bg-white rounded-2xl border border-brand-border p-6 shadow-card">
          <h2 className="font-display font-semibold text-lg text-brand-ink mb-6">
            {stepTitles[currentStep]}
          </h2>

          {renderStep(currentStep)}
        </div>
      </div>
    </div>
  );
}
