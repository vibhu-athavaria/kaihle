import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Play,
  CheckCircle,
  ThumbsUp,
  ThumbsDown,
  MessageCircle,
  AlertCircle,
  Brain,
  Sparkles,
  Zap,
} from "lucide-react";
import { StudentLayout, toast } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import {
  useSubtopicCourse,
  useMarkCourseProgress,
  useSubmitFeedback,
  useSubmitQuiz,
  useGenerateTransferQuestion,
  useGradeAnswer,
} from "../../hooks/useSubtopicCourse";
import type {
  CourseQuestion,
  CourseOption,
  GradeAnswerResult,
} from "../../types/miniCourse";
import { ExplainThisDrawer } from "../../components/mini-course/ExplainThisDrawer";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function extractYouTubeId(url: string): string | null {
  const patterns = [
    /[?&]v=([^&#]+)/,
    /youtu\.be\/([^?&#]+)/,
    /embed\/([^?&#]+)/,
  ];
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
}

/** Fire callback once when element is ≥50% visible in the viewport. */
function useIntersectionOnce(
  ref: React.RefObject<HTMLElement | null>,
  callback: () => void,
  enabled: boolean = true,
) {
  const firedRef = useRef(false);

  useEffect(() => {
    if (!enabled || !ref.current || firedRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !firedRef.current) {
          firedRef.current = true;
          observer.disconnect();
          callback();
        }
      },
      { threshold: 0.5 },
    );

    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref, callback, enabled]);
}

// ─── Learning profile pills ───────────────────────────────────────────────────

interface ProfilePill {
  icon: React.ReactNode;
  label: string;
}

function ProfilePills({
  dominant_modality,
  interest,
  work_style_label,
}: {
  dominant_modality: string | null;
  interest: string | null;
  work_style_label: string | null;
}) {
  const pills: ProfilePill[] = [];
  if (dominant_modality)
    pills.push({
      icon: <Brain className="w-3.5 h-3.5" aria-hidden="true" />,
      label: dominant_modality,
    });
  if (interest)
    pills.push({
      icon: <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />,
      label: interest,
    });
  if (work_style_label)
    pills.push({
      icon: <Zap className="w-3.5 h-3.5" aria-hidden="true" />,
      label: work_style_label,
    });

  if (pills.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {pills.map((p) => (
        <span
          key={p.label}
          className="inline-flex items-center gap-1.5 bg-brand-primary/8 text-brand-primary text-xs font-sans font-semibold px-3 py-1 rounded-full"
        >
          {p.icon}
          {p.label}
        </span>
      ))}
    </div>
  );
}

// ─── Video section ────────────────────────────────────────────────────────────

interface VideoSectionProps {
  url: string;
  onVisible: () => void;
  alreadyTracked: boolean;
}

function VideoSection({ url, onVisible, alreadyTracked }: VideoSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null);
  useIntersectionOnce(sectionRef, onVisible, !alreadyTracked);

  const videoId = extractYouTubeId(url);

  return (
    <div
      ref={sectionRef}
      id="section-video"
      className="bg-white rounded-2xl border border-brand-border p-6 space-y-4"
    >
      <div className="flex items-center gap-2">
        <Play className="w-5 h-5 text-brand-primary" aria-hidden="true" />
        <h2 className="font-display font-bold text-xl text-brand-ink">Video</h2>
      </div>
      {videoId ? (
        <div className="relative w-full" style={{ paddingTop: "56.25%" }}>
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            title="Subtopic video"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 w-full h-full rounded-xl border-0"
          />
        </div>
      ) : (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-sans text-sm text-brand-primary underline hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          Watch video
        </a>
      )}
    </div>
  );
}

// ─── Explanation card ─────────────────────────────────────────────────────────

interface ExplanationCardProps {
  explanationText: string;
  interestMatched: boolean;
  contentId: string;
  onVisible: () => void;
  alreadyTracked: boolean;
}

function ExplanationCard({
  explanationText,
  interestMatched,
  contentId,
  onVisible,
  alreadyTracked,
}: ExplanationCardProps) {
  const sectionRef = useRef<HTMLDivElement>(null);
  useIntersectionOnce(sectionRef, onVisible, !alreadyTracked);

  const [feedbackGiven, setFeedbackGiven] = useState<
    "thumbs_up" | "thumbs_down" | null
  >(null);
  const { mutate: submitFeedback, isPending } = useSubmitFeedback(contentId);

  const handleFeedback = (type: "thumbs_up" | "thumbs_down") => {
    if (feedbackGiven) return;
    submitFeedback(
      { feedback_type: type },
      {
        onSuccess: () => {
          setFeedbackGiven(type);
          toast.success("Thanks for your feedback!");
        },
        onError: () => {
          toast.error("Could not save feedback. Please try again.");
        },
      },
    );
  };

  return (
    <div
      ref={sectionRef}
      id="section-explanation"
      className="bg-white rounded-2xl border border-brand-border p-6 space-y-4"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-brand-primary" aria-hidden="true" />
          <h2 className="font-display font-bold text-xl text-brand-ink">
            Explanation
          </h2>
        </div>
        {interestMatched && (
          <span className="inline-flex items-center gap-1 bg-brand-primary/10 text-brand-primary text-xs font-sans font-semibold px-3 py-1 rounded-full">
            Personalised for you
          </span>
        )}
      </div>

      <div className="font-sans text-sm text-brand-body leading-relaxed prose prose-sm prose-p:text-brand-body prose-strong:text-brand-ink prose-headings:font-display max-w-none">
        <ReactMarkdown>{explanationText}</ReactMarkdown>
      </div>

      <div className="flex items-center gap-3 pt-2 border-t border-brand-border">
        <span className="font-sans text-xs text-brand-muted">
          Was this helpful?
        </span>
        <button
          onClick={() => handleFeedback("thumbs_up")}
          disabled={!!feedbackGiven || isPending}
          aria-label="Thumbs up — helpful"
          className={[
            "flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-sans font-semibold transition-colors",
            "focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
            feedbackGiven === "thumbs_up"
              ? "bg-brand-primary text-white"
              : "border border-brand-border text-brand-body hover:bg-brand-primary/10 hover:text-brand-primary disabled:opacity-50",
          ].join(" ")}
        >
          <ThumbsUp className="w-3.5 h-3.5" aria-hidden="true" />
          Yes
        </button>
        <button
          onClick={() => handleFeedback("thumbs_down")}
          disabled={!!feedbackGiven || isPending}
          aria-label="Thumbs down — not helpful"
          className={[
            "flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-sans font-semibold transition-colors",
            "focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
            feedbackGiven === "thumbs_down"
              ? "bg-red-500 text-white"
              : "border border-brand-border text-brand-body hover:bg-red-50 hover:text-red-500 disabled:opacity-50",
          ].join(" ")}
        >
          <ThumbsDown className="w-3.5 h-3.5" aria-hidden="true" />
          No
        </button>
      </div>
    </div>
  );
}

// ─── Check questions (MCQ) ────────────────────────────────────────────────────

const TRUE_FALSE_OPTIONS: CourseOption[] = [
  { key: "True", text: "True" },
  { key: "False", text: "False" },
];

function resolveOptions(q: CourseQuestion): CourseOption[] {
  if (q.options.length > 0) return q.options;
  const answer = q.correct_answer.toLowerCase();
  if (answer === "true" || answer === "false") return TRUE_FALSE_OPTIONS;
  return q.options;
}

interface CheckQuestionsProps {
  questions: CourseQuestion[];
  subtopicId: string;
  subtopicName: string;
  onAskTutor: (prefilledQuestion: string) => void;
}

function CheckQuestions({
  questions: initialQuestions,
  subtopicId,
  subtopicName,
  onAskTutor,
}: CheckQuestionsProps) {
  const [questions] = useState(initialQuestions);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const submitQuiz = useSubmitQuiz(subtopicId);

  const answeredCount = Object.keys(answers).length;
  const allAnswered = answeredCount === questions.length;
  const correctCount = questions.filter(
    (q) => answers[q.question_id] === q.correct_answer,
  ).length;
  const score = allAnswered ? correctCount / questions.length : null;
  const mastery = getMasteryStyle(score);

  const handleSelect = (questionId: string, key: string) => {
    if (answers[questionId]) return;
    const next = { ...answers, [questionId]: key };
    setAnswers(next);
    if (Object.keys(next).length === questions.length) {
      submitQuiz.mutate({
        answers: Object.entries(next).map(([question_id, selected_key]) => ({
          question_id,
          selected_key,
        })),
      });
    }
  };

  const handleAskTutor = (q: CourseQuestion) => {
    onAskTutor(
      `I got this question wrong. Can you explain why the correct answer is "${q.correct_answer}"?\n\nQuestion: ${q.question_text}`,
    );
  };

  return (
    <div
      id="section-quiz"
      className="bg-white rounded-2xl border border-brand-border p-6 space-y-6"
    >
      <div className="flex items-center gap-2">
        <CheckCircle
          className="w-5 h-5 text-brand-primary"
          aria-hidden="true"
        />
        <h2 className="font-display font-bold text-xl text-brand-ink">
          Check Your Understanding
        </h2>
      </div>

      <ol className="space-y-0">
        {questions.map((q, idx) => {
          const chosen = answers[q.question_id];
          const isCorrect = chosen === q.correct_answer;
          const opts = resolveOptions(q);

          return (
            <li
              key={q.question_id}
              className={`space-y-3 py-5 ${idx > 0 ? "border-t border-brand-border" : ""}`}
            >
              <p className="font-sans font-semibold text-sm text-brand-ink">
                {idx + 1}. {q.question_text}
              </p>
              <ul className="space-y-2 list-none">
                {opts.map((opt) => {
                  const isChosen = chosen === opt.key;
                  const isCorrectOpt = opt.key === q.correct_answer;
                  let optClass =
                    "w-full text-left px-4 py-3 rounded-xl border font-sans text-sm transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 flex items-center gap-2";

                  if (!chosen) {
                    optClass +=
                      " border-brand-border text-brand-body hover:border-brand-primary hover:bg-brand-primary/5";
                  } else if (isCorrectOpt) {
                    optClass +=
                      " border-brand-green bg-brand-green-light text-brand-green-dark font-semibold";
                  } else if (isChosen && !isCorrect) {
                    optClass +=
                      " border-brand-red bg-brand-red-light text-brand-red-dark";
                  } else {
                    optClass += " border-brand-border text-brand-muted";
                  }

                  return (
                    <li key={opt.key}>
                      <button
                        onClick={() => handleSelect(q.question_id, opt.key)}
                        disabled={!!chosen}
                        className={optClass}
                      >
                        <span className="w-5 h-5 rounded-full border border-current flex-shrink-0 flex items-center justify-center text-xs font-bold">
                          {opt.key.length === 1 ? opt.key : opt.key[0]}
                        </span>
                        {opt.text}
                      </button>
                    </li>
                  );
                })}
              </ul>

              {chosen && !isCorrect && (
                <button
                  onClick={() => handleAskTutor(q)}
                  className="flex items-center gap-1.5 text-xs font-sans font-semibold text-brand-primary hover:text-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
                >
                  <MessageCircle className="w-3.5 h-3.5" aria-hidden="true" />
                  Ask AI tutor to explain this
                </button>
              )}
            </li>
          );
        })}
      </ol>

      {allAnswered && (
        <div
          className={`rounded-xl p-4 flex items-center gap-3 ${mastery.bgClass}`}
        >
          <span
            className={`w-3 h-3 rounded-full flex-shrink-0 ${mastery.dotClass}`}
            aria-label={mastery.label}
            role="img"
          />
          <p className={`font-sans font-semibold text-sm ${mastery.textClass}`}>
            {correctCount}/{questions.length} correct — {mastery.label}
          </p>
        </div>
      )}

      <p className="font-sans text-xs text-brand-muted">
        {subtopicName} · Multiple choice questions
      </p>
    </div>
  );
}

// ─── Transfer question component ──────────────────────────────────────────────

interface TransferQuestionProps {
  subtopicId: string;
  initialAnswer?: {
    question_text: string;
    student_answer: string;
    ai_grade: string | null;
    ai_feedback: string | null;
    score: number;
  } | null;
}

const GRADE_STYLES: Record<
  "correct" | "partial" | "incorrect",
  { bg: string; text: string; label: string }
> = {
  correct: {
    bg: "bg-brand-green-light border-brand-green",
    text: "text-brand-green-dark",
    label: "Correct",
  },
  partial: {
    bg: "bg-brand-amber-light border-brand-amber",
    text: "text-brand-amber-dark",
    label: "Partially correct",
  },
  incorrect: {
    bg: "bg-brand-red-light border-brand-red",
    text: "text-brand-red-dark",
    label: "Needs more work",
  },
};

function TransferQuestionSection({
  subtopicId,
  initialAnswer,
}: TransferQuestionProps) {
  const [questionText, setQuestionText] = useState<string | null>(
    initialAnswer?.question_text ?? null,
  );
  const [answerText, setAnswerText] = useState(
    initialAnswer?.student_answer ?? "",
  );
  const [result, setResult] = useState<GradeAnswerResult | null>(null);
  const [hasRestored] = useState(!!initialAnswer?.ai_grade);

  const generateQuestion = useGenerateTransferQuestion(subtopicId);
  const gradeAnswer = useGradeAnswer(subtopicId);

  const handleGenerate = () => {
    generateQuestion.mutate(undefined, {
      onSuccess: (data) => setQuestionText(data.question_text),
      onError: () => toast.error("Couldn't generate a question. Try again."),
    });
  };

  const handleSubmit = () => {
    if (!questionText || !answerText.trim()) return;
    gradeAnswer.mutate(
      { question_text: questionText, student_answer: answerText.trim() },
      {
        onSuccess: (data) => setResult(data),
        onError: () => toast.error("Couldn't grade your answer. Try again."),
      },
    );
  };

  const handleRetry = () => {
    setAnswerText("");
    setResult(null);
    setQuestionText(null);
  };

  const gradeStyle =
    result?.grade && result.grade in GRADE_STYLES
      ? GRADE_STYLES[result.grade as keyof typeof GRADE_STYLES]
      : null;

  return (
    <div
      id="section-transfer"
      className="bg-white rounded-2xl border border-brand-border p-6 space-y-5"
    >
      <div className="flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-brand-primary" aria-hidden="true" />
        <h2 className="font-display font-bold text-xl text-brand-ink">
          Challenge Question
        </h2>
      </div>
      <p className="font-sans text-sm text-brand-body">
        Apply what you've learnt to a new scenario. There's no multiple choice
        here — explain your thinking in your own words.
      </p>

      {/* Restored previous answer */}
      {hasRestored && initialAnswer?.ai_grade && (
        <div className="rounded-xl border bg-gray-50 p-4 space-y-2">
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted">
            Your previous answer
          </p>
          <p className="font-sans text-sm text-brand-ink font-semibold">
            {initialAnswer.question_text}
          </p>
          <p className="font-sans text-sm text-brand-body">
            {initialAnswer.student_answer}
          </p>
          <div
            className={`rounded-lg border p-3 mt-2 ${GRADE_STYLES[initialAnswer.ai_grade as keyof typeof GRADE_STYLES]?.bg ?? ""}`}
          >
            <p
              className={`font-sans text-xs font-bold uppercase mb-1 ${GRADE_STYLES[initialAnswer.ai_grade as keyof typeof GRADE_STYLES]?.text ?? ""}`}
            >
              {GRADE_STYLES[initialAnswer.ai_grade as keyof typeof GRADE_STYLES]
                ?.label ?? initialAnswer.ai_grade}
            </p>
            <p className="font-sans text-sm text-brand-ink">
              {initialAnswer.ai_feedback}
            </p>
          </div>
          <button
            onClick={handleRetry}
            className="font-sans text-xs font-semibold text-brand-primary hover:text-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded mt-1"
          >
            Try a new question →
          </button>
        </div>
      )}

      {!hasRestored && !questionText && (
        <button
          onClick={handleGenerate}
          disabled={generateQuestion.isPending}
          className="flex items-center gap-2 px-5 py-2.5 bg-brand-primary text-white rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50"
        >
          <Sparkles className="w-4 h-4" aria-hidden="true" />
          {generateQuestion.isPending
            ? "Generating..."
            : "Get a challenge question"}
        </button>
      )}

      {!hasRestored && questionText && !result && (
        <div className="space-y-4">
          <div className="rounded-xl bg-brand-primary/5 border border-brand-primary/20 p-4">
            <p className="font-sans text-sm text-brand-ink font-semibold">
              {questionText}
            </p>
          </div>
          <div>
            <label
              htmlFor="transfer-answer"
              className="font-sans text-sm font-semibold text-brand-ink mb-1.5 block"
            >
              Your answer
            </label>
            <textarea
              id="transfer-answer"
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              maxLength={1000}
              rows={5}
              placeholder="Explain your thinking in 2–5 sentences..."
              className="w-full rounded-xl border border-brand-border p-3 font-sans text-sm text-brand-ink placeholder-brand-muted resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            />
            <p className="font-sans text-xs text-brand-muted text-right mt-1">
              {answerText.length} / 1000
            </p>
          </div>
          <button
            onClick={handleSubmit}
            disabled={!answerText.trim() || gradeAnswer.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-primary text-white rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {gradeAnswer.isPending ? "Grading..." : "Submit answer"}
          </button>
        </div>
      )}

      {!hasRestored && result && gradeStyle && (
        <div className="space-y-4">
          <div className="rounded-xl bg-brand-primary/5 border border-brand-primary/20 p-4">
            <p className="font-sans text-sm text-brand-ink font-semibold">
              {questionText}
            </p>
          </div>
          <div className="rounded-xl border p-4 bg-gray-50">
            <p className="font-sans text-xs text-brand-muted mb-1">
              Your answer
            </p>
            <p className="font-sans text-sm text-brand-body">{answerText}</p>
          </div>
          <div className={`rounded-xl border p-4 ${gradeStyle.bg}`}>
            <p
              className={`font-sans text-xs font-bold uppercase tracking-widest mb-1.5 ${gradeStyle.text}`}
            >
              {gradeStyle.label}
            </p>
            <p className="font-sans text-sm text-brand-ink">
              {result.feedback}
            </p>
          </div>
          <button
            onClick={handleRetry}
            className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          >
            Try another question →
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Page skeleton ─────────────────────────────────────────────────────────────

function MiniCourseSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-6 w-2/3 bg-brand-border rounded-full" />
      <div className="h-32 bg-brand-border rounded-2xl" />
      <div className="h-52 bg-brand-border rounded-2xl" />
      <div className="h-72 bg-brand-border rounded-2xl" />
      <div className="h-64 bg-brand-border rounded-2xl" />
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export function MiniCoursePage() {
  const { subtopicId } = useParams<{ subtopicId: string }>();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();
  const [explainOpen, setExplainOpen] = useState(false);
  const [explainPrefill, setExplainPrefill] = useState("");

  const { data: course, isPending, isError } = useSubtopicCourse(subtopicId!);
  const { mutate: markProgress } = useMarkCourseProgress(subtopicId!);

  const handleVideoVisible = useCallback(() => {
    markProgress({ video_accessed: true });
  }, [markProgress]);

  const handleExplanationVisible = useCallback(() => {
    markProgress({ explanation_accessed: true });
  }, [markProgress]);

  const handleAskTutor = (prefill: string) => {
    setExplainPrefill(prefill);
    setExplainOpen(true);
  };

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/student/dashboard");
    }
  };

  if (isError) {
    return (
      <StudentLayout
        activeNav="home"
        studentName={layout.studentName}
        gradeName={layout.gradeName}
        curriculumName={layout.curriculumName}
        classes={layout.sidebarClasses}
        onLogout={layout.onLogout}
      >
        <div className="text-center py-16">
          <AlertCircle
            className="w-10 h-10 text-brand-muted mx-auto mb-4"
            aria-hidden="true"
          />
          <p className="font-sans text-sm text-brand-body">
            Something went wrong loading the mini-course. Please refresh the
            page.
          </p>
        </div>
      </StudentLayout>
    );
  }

  return (
    <StudentLayout
      activeNav="home"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      onLogout={layout.onLogout}
    >
      <div className="space-y-6">
        {/* Back breadcrumb */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={handleBack}
            className="flex items-center gap-1 text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            Back
          </button>
          {course && (
            <>
              <span className="text-brand-muted">/</span>
              <span className="text-brand-muted">{course.topic_name}</span>
              <span className="text-brand-muted">/</span>
              <span className="text-brand-ink font-medium">
                {course.subtopic_name}
              </span>
            </>
          )}
        </div>

        {isPending ? (
          <MiniCourseSkeleton />
        ) : course ? (
          <>
            {/* Header with learning profile pills */}
            <div className="bg-white rounded-2xl border border-brand-border p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h1 className="font-display font-bold text-2xl text-brand-ink mb-0.5">
                    {course.subtopic_name}
                  </h1>
                  <p className="font-sans text-sm text-brand-muted">
                    {course.topic_name}
                  </p>
                  {course.learning_profile && (
                    <ProfilePills {...course.learning_profile} />
                  )}
                </div>
                <button
                  onClick={() => {
                    setExplainPrefill("");
                    setExplainOpen(true);
                  }}
                  className="flex-shrink-0 flex items-center gap-1.5 border border-brand-primary text-brand-primary rounded-full px-4 py-2 text-sm font-sans font-semibold hover:bg-brand-primary/10 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                >
                  <MessageCircle className="w-4 h-4" aria-hidden="true" />
                  AI Tutor
                </button>
              </div>
            </div>

            {/* Video */}
            {course.video ? (
              <VideoSection
                url={course.video.video_url}
                onVisible={handleVideoVisible}
                alreadyTracked={course.progress.video_accessed}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-brand-border p-10 text-center">
                <Play
                  className="w-10 h-10 text-brand-muted mx-auto mb-3"
                  aria-hidden="true"
                />
                <h2 className="font-display font-bold text-lg text-brand-ink mb-1">
                  No video yet
                </h2>
                <p className="font-sans text-sm text-brand-body">
                  A video for this subtopic hasn't been added yet.
                </p>
              </div>
            )}

            {/* Explanation */}
            {course.explanation ? (
              <ExplanationCard
                explanationText={course.explanation.explanation_text}
                interestMatched={course.explanation.interest_matched}
                contentId={String(course.explanation.content_id)}
                onVisible={handleExplanationVisible}
                alreadyTracked={course.progress.explanation_accessed}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-brand-border p-10 text-center">
                <BookOpen
                  className="w-10 h-10 text-brand-muted mx-auto mb-3"
                  aria-hidden="true"
                />
                <h2 className="font-display font-bold text-lg text-brand-ink mb-1">
                  No explanation yet
                </h2>
                <p className="font-sans text-sm text-brand-body">
                  Your teacher hasn't generated an explanation for this subtopic
                  yet. Check back soon.
                </p>
              </div>
            )}

            {/* MCQ quiz */}
            {(course.check_questions ?? []).length > 0 ? (
              <CheckQuestions
                questions={course.check_questions}
                subtopicId={subtopicId!}
                subtopicName={course.subtopic_name}
                onAskTutor={handleAskTutor}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-brand-border p-10 text-center">
                <CheckCircle
                  className="w-10 h-10 text-brand-muted mx-auto mb-3"
                  aria-hidden="true"
                />
                <h2 className="font-display font-bold text-lg text-brand-ink mb-1">
                  No quiz questions yet
                </h2>
                <p className="font-sans text-sm text-brand-body">
                  Quiz questions for this subtopic haven't been added yet.
                </p>
              </div>
            )}

            {/* AI transfer question */}
            <TransferQuestionSection
              subtopicId={subtopicId!}
              initialAnswer={course.latest_open_answer}
            />

            {/* Next subtopic navigation */}
            {course.next_subtopic && (
              <div className="flex justify-end pb-4">
                <button
                  onClick={() =>
                    navigate(
                      `/student/subtopics/${course.next_subtopic!.id}/course`,
                    )
                  }
                  className="flex items-center gap-2 bg-brand-primary text-white rounded-full px-5 py-2.5 text-sm font-sans font-semibold hover:bg-brand-primary/90 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                >
                  Next: {course.next_subtopic.name}
                  <ArrowRight className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            )}
          </>
        ) : null}
      </div>

      <ExplainThisDrawer
        open={explainOpen}
        onClose={() => setExplainOpen(false)}
        subtopicId={subtopicId!}
        subtopicName={course?.subtopic_name ?? "this subtopic"}
        initialQuestion={explainPrefill}
      />
    </StudentLayout>
  );
}
