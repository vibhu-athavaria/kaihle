import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Check } from "lucide-react";
import { OnboardingLayout } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import {
  useQuestionnaireStore,
  QUESTION_KEYS,
} from "../../store/questionnaireStore";
import { apiClient } from "@kaihle/auth";

// Types for API questionnaire response
interface QuestionnaireOption {
  key: string;
  text: string;
  emoji?: string;
}

interface QuestionnaireQuestion {
  id: string;
  text: string;
  type: string;
  options: QuestionnaireOption[];
}

interface QuestionnaireDefinition {
  version: string;
  questions: QuestionnaireQuestion[];
}

export function ProfileQuestionnaire() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [questionnaire, setQuestionnaire] =
    useState<QuestionnaireDefinition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { answers, setAnswer, toggleInterest, nextStep, prevStep } =
    useQuestionnaireStore();

  // Fetch questionnaire from API
  useEffect(() => {
    const fetchQuestionnaire = async () => {
      try {
        const response = await apiClient.get<QuestionnaireDefinition>(
          "/api/v1/onboarding/questionnaire",
        );
        setQuestionnaire(response.data);
      } catch {
        setError("Failed to load questionnaire");
      } finally {
        setIsLoading(false);
      }
    };

    fetchQuestionnaire();
  }, []);

  const totalQuestions = questionnaire?.questions.length ?? 6;

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      // Build responses in the format expected by backend
      const responses =
        questionnaire?.questions.map((q, index) => {
          if (q.type === "multi_select") {
            return { question_id: q.id, answer_keys: answers.interests };
          }
          const questionKey = QUESTION_KEYS[index];
          return { question_id: q.id, answer_key: answers[questionKey] };
        }) ?? [];

      await apiClient.post("/api/v1/onboarding/questionnaire/submit", {
        responses,
      });
      navigate("/student/dashboard");
    } catch {
      setError("Something went wrong, please try again");
    } finally {
      setIsSubmitting(false);
    }
  };

  const canProceed = () => {
    if (currentStep <= 5 && questionnaire) {
      const question = questionnaire.questions[currentStep - 1];
      if (question.type === "multi_select") {
        return true; // Multi-select is optional
      }
      const questionKey = QUESTION_KEYS[currentStep - 1];
      return answers[questionKey] !== null;
    }
    return true;
  };

  const renderQuestion = () => {
    if (!questionnaire) return null;

    const question = questionnaire.questions[currentStep - 1];
    if (!question) return null;

    if (question.type === "multi_select") {
      return (
        <div className="space-y-6">
          <h2 className="font-display font-bold text-xl text-brand-ink text-center">
            What are you interested in?
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {question.options.map((option) => {
              const isSelected = answers.interests.includes(option.key);
              return (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => toggleInterest(option.key)}
                  className={`
                    relative p-4 rounded-xl border-2 transition-all min-h-[44px]
                    ${
                      isSelected
                        ? "border-brand-primary bg-brand-green-light"
                        : "border-brand-border hover:border-brand-mid"
                    }
                  `}
                >
                  <span className="text-2xl block">{option.emoji}</span>
                  <span className="text-xs font-semibold text-brand-ink mt-2 block">
                    {option.text}
                  </span>
                  {isSelected && (
                    <span className="absolute top-2 right-2 w-5 h-5 bg-brand-primary rounded-full flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      );
    }

    // Single select question
    const questionKey = QUESTION_KEYS[currentStep - 1];
    const currentValue = answers[questionKey];

    return (
      <div className="space-y-6">
        <h2 className="font-display font-bold text-xl text-brand-ink text-center">
          {question.text}
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {question.options.map((option) => {
            const isSelected = currentValue === option.key;
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => setAnswer(questionKey, option.key)}
                className={`
                  relative p-6 rounded-xl border-2 transition-all text-left min-h-[44px]
                  ${
                    isSelected
                      ? "border-brand-primary bg-brand-green-light"
                      : "border-brand-border hover:border-brand-mid"
                  }
                `}
              >
                {isSelected && (
                  <span className="absolute top-3 right-3 w-5 h-5 bg-brand-primary rounded-full flex items-center justify-center">
                    <Check className="w-3 h-3 text-white" />
                  </span>
                )}
                <span className="text-sm font-semibold text-brand-ink block">
                  {option.text}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  if (isLoading) {
    return (
      <OnboardingLayout
        step={currentStep}
        totalSteps={totalQuestions}
        stepLabel="Learning profile"
      >
        <div className="text-center py-8">Loading questionnaire...</div>
      </OnboardingLayout>
    );
  }

  if (error && !questionnaire) {
    return (
      <OnboardingLayout
        step={currentStep}
        totalSteps={totalQuestions}
        stepLabel="Learning profile"
      >
        <div className="text-center py-8">
          <p className="text-brand-red">{error}</p>
        </div>
      </OnboardingLayout>
    );
  }

  return (
    <OnboardingLayout
      step={currentStep}
      totalSteps={totalQuestions}
      stepLabel="Learning profile"
    >
      <div className="max-w-2xl mx-auto">
        {error && (
          <div className="mb-4 p-3 bg-brand-red-light text-brand-red rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="mb-8">{renderQuestion()}</div>

        <div className="flex justify-between">
          <Button
            variant="secondary"
            onClick={() => {
              prevStep();
              setCurrentStep((s) => Math.max(1, s - 1));
            }}
            disabled={currentStep === 1}
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </Button>

          {currentStep === totalQuestions ? (
            <Button
              onClick={handleSubmit}
              loading={isSubmitting}
              disabled={!canProceed()}
            >
              Submit
            </Button>
          ) : (
            <Button
              onClick={() => {
                nextStep();
                setCurrentStep((s) => Math.min(totalQuestions, s + 1));
              }}
              disabled={!canProceed()}
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    </OnboardingLayout>
  );
}
