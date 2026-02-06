import React, { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  ChevronRight,
  ChevronLeft,
  Brain,
  Loader2,
  AlertCircle
} from "lucide-react";

import { http } from "@/lib/http";
import { IntakeForm, IntakeQuestion, IntakeAnswers } from "../types/learningProfile";

interface LearningProfileIntakeFormProps {
    onSubmit: (answers: IntakeAnswers) => Promise<void>;
    onSkip?: () => void;
}

// --- Wizard Helper Types ---
interface WizardStep {
  sectionTitle: string;
  sectionDescription?: string;
  question: IntakeQuestion;
  stepIndex: number;
  totalSteps: number;
}


const LearningProfileIntakeForm: React.FC<LearningProfileIntakeFormProps> = ({
  onSubmit,
  onSkip
}) => {
  const [formSchema, setFormSchema] = useState<IntakeForm | null>(null);
  const [answers, setAnswers] = useState<IntakeAnswers>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Wizard State
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [direction, setDirection] = useState(0); // 1 for next, -1 for back

  // Simulate API Call
  useEffect(() => {
    const fetchIntakeForm = async () => {
      setLoading(true);
      try {
        const response = await http.get("/api/v1/students/learning-profile/intake-form")
        setFormSchema(response.data)
      } catch (err) {
        setError("Failed to load learning profile form.");
      } finally {
        setLoading(false);
      }
    };
    fetchIntakeForm();
  }, []);

  // Flatten the form structure into linear steps
  const wizardSteps = useMemo(() => {
    if (!formSchema) return [];
    const steps: WizardStep[] = [];
    formSchema.sections.forEach(section => {
      section.questions.forEach(question => {
        steps.push({
          sectionTitle: section.title,
          sectionDescription: section.description,
          question,
          stepIndex: steps.length,
          totalSteps: 0 // Will fill this after
        });
      });
    });
    return steps.map(step => ({ ...step, totalSteps: steps.length }));
  }, [formSchema]);

  const currentStep = wizardSteps[currentStepIndex];

  const updateSingleSelect = (questionId: string, value: string) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: value
    }));
  };

  const updateMultiSelect = (question: IntakeQuestion, value: string) => {
    setAnswers(prev => {
      const current = (prev[question.question_id] as string[]) || [];
      const exists = current.includes(value);

      if (exists) {
        return {
          ...prev,
          [question.question_id]: current.filter(v => v !== value)
        };
      }

      if (question.max_selections && current.length >= question.max_selections) {
        return prev;
      }

      return {
        ...prev,
        [question.question_id]: [...current, value]
      };
    });
  };

  const handleNext = () => {
    if (currentStepIndex < wizardSteps.length - 1) {
      setDirection(1);
      setCurrentStepIndex(prev => prev + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setDirection(-1);
      setCurrentStepIndex(prev => prev - 1);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await onSubmit(answers);
    } catch {
      setError("Failed to submit learning profile. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const isCurrentStepValid = () => {
    if (!currentStep) return false;
    const answer = answers[currentStep.question.question_id];
    if (currentStep.question.type === "multi_select") {
      return Array.isArray(answer) && answer.length > 0;
    }
    return !!answer;
  };

  // Animation variants
  const slideVariants = {
    enter: (direction: number) => ({
      x: direction > 0 ? 50 : -50,
      opacity: 0,
      scale: 0.95
    }),
    center: {
      zIndex: 1,
      x: 0,
      opacity: 1,
      scale: 1
    },
    exit: (direction: number) => ({
      zIndex: 0,
      x: direction < 0 ? 50 : -50,
      opacity: 0,
      scale: 0.95
    })
  };

  if (loading) {
    return (
      <div className="min-h-[400px] flex flex-col items-center justify-center p-8 text-center">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <h3 className="text-xl font-semibold text-gray-700">Loading your profile...</h3>
      </div>
    );
  }

  if (error || !currentStep) {
    return (
      <div className="min-h-[400px] flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
          <AlertCircle className="w-8 h-8 text-red-500" />
        </div>
        <h3 className="text-xl font-bold text-gray-800 mb-2">Oops! Something went wrong</h3>
        <p className="text-gray-600 mb-6">{error || "Failed to load form"}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-6 py-2 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  const progressPercentage = ((currentStepIndex + 1) / wizardSteps.length) * 100;

  return (
    <div className="w-full max-w-4xl mx-auto p-4 sm:p-6 flex flex-col min-h-[600px] bg-white">
      {/* Header & Progress */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
              <Brain className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">
                Profile Builder
              </h1>
              <p className="text-sm text-gray-500">
                Step {currentStepIndex + 1} of {wizardSteps.length}
              </p>
            </div>
          </div>
          {onSkip && (
            <button
              onClick={onSkip}
              className="text-sm font-semibold text-gray-400 hover:text-gray-600 transition-colors"
            >
              Skip
            </button>
          )}
        </div>

        <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercentage}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Main Card Area */}
      <div className="flex-1 relative overflow-hidden flex flex-col">
        <AnimatePresence initial={false} custom={direction} mode="wait">
          <motion.div
            key={currentStep.question.question_id}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{
              x: { type: "spring", stiffness: 300, damping: 30 },
              opacity: { duration: 0.2 }
            }}
            className="flex-1 flex flex-col justify-center"
          >
            {/* Section Info */}
            <div className="text-center mb-8">
              <span className="inline-block px-3 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-bold uppercase tracking-wide mb-3">
                {currentStep.sectionTitle}
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-800 mb-4">
                {currentStep.question.label}
              </h2>
              {currentStep.sectionDescription && (
                <p className="text-lg text-gray-500 max-w-xl mx-auto">
                  {currentStep.sectionDescription}
                </p>
              )}
              {currentStep.question.max_selections && (
                <p className="mt-2 text-sm text-blue-600 font-medium">
                  Select up to {currentStep.question.max_selections} options
                </p>
              )}
            </div>

            {/* Options Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-3xl mx-auto w-full">
              {currentStep.question.options.map((option) => {
                const isSelected = currentStep.question.type === "single_select"
                  ? answers[currentStep.question.question_id] === option.value
                  : (answers[currentStep.question.question_id] as string[] || []).includes(option.value);

                return (
                  <motion.button
                    key={option.value}
                    whileHover={{ scale: 0.99 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() =>
                      currentStep.question.type === "single_select"
                        ? updateSingleSelect(currentStep.question.question_id, option.value)
                        : updateMultiSelect(currentStep.question, option.value)
                    }
                    className={`
                      relative group text-left rounded-2xl p-5 border-2 transition-all duration-200 w-full
                      ${isSelected
                        ? "border-blue-500 bg-purple-100 shadow-lg shadow-blue-200/50 ring-1 ring-blue-500/20"
                        : "border-gray-200 bg-purple-50 hover:border-blue-300 hover:bg-white hover:shadow-md"
                      }
                    `}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`
                        w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors
                        ${isSelected ? "border-blue-500 bg-blue-500" : "border-gray-300 group-hover:border-blue-400"}
                      `}>
                        {isSelected && <Check className="w-3.5 h-3.5 text-white stroke-[3]" />}
                      </div>

                      <div>
                        <span className={`block text-lg font-bold mb-0.5 ${isSelected ? "text-blue-700" : "text-gray-800"}`}>
                          {option.label}
                        </span>
                        {option.description && (
                          <span className="text-sm text-gray-500 block">
                            {option.description}
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Footer Navigation */}
      <div className="mt-10 flex items-center justify-between border-t border-gray-100 pt-6">
        <button
          onClick={handleBack}
          disabled={currentStepIndex === 0 || submitting}
          className={`
            flex items-center gap-2 px-6 py-3 rounded-xl font-bold transition-colors
            ${currentStepIndex === 0
              ? "text-gray-300 cursor-not-allowed"
              : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            }
          `}
        >
          <ChevronLeft className="w-5 h-5" />
          Back
        </button>

        <button
          onClick={handleNext}
          disabled={!isCurrentStepValid() || submitting}
          className={`
            flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-white shadow-lg transition-all duration-200
            ${!isCurrentStepValid() || submitting
              ? "bg-gray-300 cursor-not-allowed shadow-none"
              : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:translate-y-[-2px] hover:shadow-blue-500/30 active:translate-y-0"
            }
          `}
        >
          {submitting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            currentStepIndex === wizardSteps.length - 1 ? "Finish" : "Next"
          )}
          {!submitting && currentStepIndex !== wizardSteps.length - 1 && (
            <ChevronRight className="w-5 h-5" />
          )}
        </button>
      </div>
    </div>
  );
};

export default LearningProfileIntakeForm;
