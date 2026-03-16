import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Video,
  BookOpen,
  Wrench,
  MessageCircle,
  Clock,
  Users,
  Globe,
  Brain,
  Sparkles,
  Target,
  ChevronLeft,
  ChevronRight,
  Check,
} from "lucide-react";
import { OnboardingLayout } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import {
  useQuestionnaireStore,
  type QuestionKey,
} from "../../store/questionnaireStore";
import { apiClient } from "@kaihle/auth";

const QUESTION_KEYS: QuestionKey[] = [
  "q1_preferred_medium",
  "q2_learning_pace",
  "q3_help_preference",
  "q4_environment",
  "q5_goal",
];

const QUESTIONS = [
  {
    id: "q1",
    question: "How do you prefer to learn new concepts?",
    options: [
      { value: "video", label: "Video tutorials", icon: Video },
      { value: "reading", label: "Reading materials", icon: BookOpen },
      { value: "hands_on", label: "Hands-on practice", icon: Wrench },
      { value: "discussion", label: "Discussion", icon: MessageCircle },
    ],
  },
  {
    id: "q2",
    question: "What's your preferred learning pace?",
    options: [
      {
        value: "self_paced",
        label: "I like to go at my own speed",
        icon: Clock,
      },
      {
        value: "structured",
        label: "I prefer a structured schedule",
        icon: Users,
      },
      { value: "flexible", label: "Flexible with some guidance", icon: Globe },
      { value: "immersive", label: "Immersive deep dives", icon: Brain },
    ],
  },
  {
    id: "q3",
    question: "When you need help, what works best?",
    options: [
      { value: "immediate", label: "Immediate feedback", icon: Sparkles },
      { value: "research", label: "Time to figure it out", icon: BookOpen },
      { value: "peer", label: "Discuss with peers", icon: Users },
      {
        value: "teacher",
        label: "Ask the teacher directly",
        icon: MessageCircle,
      },
    ],
  },
  {
    id: "q4",
    question: "Where do you study best?",
    options: [
      { value: "quiet", label: "Quiet space alone", icon: BookOpen },
      { value: "collaborative", label: "With others", icon: Users },
      { value: "varied", label: "Different places", icon: Globe },
      { value: "flexible", label: "Anywhere", icon: Wrench },
    ],
  },
  {
    id: "q5",
    question: "What's your main learning goal?",
    options: [
      { value: "mastery", label: "Master subjects deeply", icon: Target },
      { value: "grades", label: "Improve grades", icon: BookOpen },
      { value: "practical", label: "Apply to real life", icon: Wrench },
      { value: "confidence", label: "Build confidence", icon: Sparkles },
    ],
  },
];

const INTERESTS = [
  { id: "sports", emoji: "⚽", label: "Sports" },
  { id: "music", emoji: "🎵", label: "Music" },
  { id: "art", emoji: "🎨", label: "Art" },
  { id: "gaming", emoji: "🎮", label: "Gaming" },
  { id: "reading", emoji: "📚", label: "Reading" },
  { id: "science", emoji: "🔬", label: "Science" },
  { id: "nature", emoji: "🌿", label: "Nature" },
  { id: "cooking", emoji: "🍳", label: "Cooking" },
  { id: "travel", emoji: "✈️", label: "Travel" },
  { id: "tech", emoji: "💻", label: "Tech" },
];

export function ProfileQuestionnaire() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    answers,
    currentStep,
    setAnswer,
    toggleInterest,
    nextStep,
    prevStep,
  } = useQuestionnaireStore();

  const totalQuestions = 6;

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      // Build responses in the format expected by backend
      const responses = [
        { question_id: "q1", answer_key: answers.q1_preferred_medium },
        { question_id: "q2", answer_key: answers.q2_learning_pace },
        { question_id: "q3", answer_key: answers.q3_help_preference },
        { question_id: "q4", answer_key: answers.q4_environment },
        { question_id: "q5", answer_key: answers.q5_goal },
        { question_id: "q6_to_q10", answer_keys: answers.interests },
      ];

      await apiClient.post("/api/v1/onboarding/questionnaire/submit", {
        responses,
      });
      navigate("/student/onboarding/diagnostics");
    } catch {
      setError("Something went wrong, please try again");
    } finally {
      setIsSubmitting(false);
    }
  };

  const canProceed = () => {
    if (currentStep <= 5) {
      const questionKey = QUESTION_KEYS[currentStep - 1];
      return answers[questionKey] !== null;
    }
    return true;
  };

  const renderQuestion = () => {
    if (currentStep === 6) {
      return (
        <div className="space-y-6">
          <h2 className="font-display font-bold text-xl text-brand-ink text-center">
            What are you interested in? (Optional)
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {INTERESTS.map((interest) => {
              const isSelected = answers.interests.includes(interest.id);
              return (
                <button
                  key={interest.id}
                  type="button"
                  onClick={() => toggleInterest(interest.id)}
                  className={[
                    "relative flex flex-col items-center justify-center p-4 rounded-2xl border-2 transition-all min-h-[80px]",
                    isSelected
                      ? "border-brand-primary bg-brand-light"
                      : "border-brand-border hover:border-brand-mid bg-white",
                  ].join(" ")}
                  aria-pressed={isSelected}
                  aria-label={`${interest.label} ${
                    isSelected ? "selected" : "not selected"
                  }`}
                >
                  <span className="text-3xl mb-1" role="img" aria-hidden="true">
                    {interest.emoji}
                  </span>
                  <span className="text-xs font-semibold text-brand-body">
                    {interest.label}
                  </span>
                  {isSelected && (
                    <div className="absolute top-2 right-2 w-5 h-5 bg-brand-primary rounded-full flex items-center justify-center">
                      <Check
                        className="w-3 h-3 text-white"
                        aria-hidden="true"
                      />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      );
    }

    const q = QUESTIONS[currentStep - 1];
    const answerKey = QUESTION_KEYS[currentStep - 1];

    return (
      <div className="space-y-6">
        <h2 className="font-display font-bold text-xl text-brand-ink text-center">
          {q.question}
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {q.options.map((option) => {
            const isSelected = answers[answerKey] === option.value;
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setAnswer(answerKey, option.value)}
                className={[
                  "flex flex-col items-center justify-center p-6 rounded-2xl border-2 transition-all min-h-[120px]",
                  isSelected
                    ? "border-brand-primary bg-brand-light shadow-card-hover"
                    : "border-brand-border hover:border-brand-mid bg-white",
                ].join(" ")}
                aria-pressed={isSelected}
                aria-label={option.label}
              >
                <Icon
                  className={`w-8 h-8 mb-3 ${
                    isSelected ? "text-brand-primary" : "text-brand-body"
                  }`}
                  aria-hidden="true"
                />
                <span className="text-sm font-semibold text-brand-ink text-center">
                  {option.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <OnboardingLayout
      step={currentStep}
      totalSteps={totalQuestions}
      stepLabel="Learning Profile"
    >
      {error && (
        <div className="mb-4 p-3 bg-brand-red-light text-brand-red rounded-lg text-sm font-semibold">
          {error}
        </div>
      )}

      {renderQuestion()}

      <div className="flex justify-between mt-8">
        <Button
          variant="secondary"
          onClick={prevStep}
          disabled={currentStep === 1}
          icon={<ChevronLeft className="w-4 h-4" />}
        >
          Back
        </Button>
        {currentStep < totalQuestions ? (
          <Button
            onClick={nextStep}
            disabled={!canProceed()}
            icon={<ChevronRight className="w-4 h-4" />}
          >
            Next
          </Button>
        ) : (
          <Button onClick={handleSubmit} loading={isSubmitting}>
            Submit
          </Button>
        )}
      </div>
    </OnboardingLayout>
  );
}
