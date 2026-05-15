import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Play,
  CheckCircle,
  ThumbsUp,
  ThumbsDown,
  MessageCircle,
  AlertCircle,
} from "lucide-react";
import { StudentLayout, toast } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import {
  useSubtopicCourse,
  useMarkCourseProgress,
  useSubmitFeedback,
} from "../../hooks/useSubtopicCourse";
import type { CourseQuestion } from "../../types/miniCourse";
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

// ─── Sub-components ───────────────────────────────────────────────────────────

interface ExplanationCardProps {
  explanationText: string;
  interestCategory: string | null;
  contentId: string;
}

function ExplanationCard({
  explanationText,
  interestCategory,
  contentId,
}: ExplanationCardProps) {
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
    <div className="bg-white rounded-2xl border border-brand-border p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-brand-primary" aria-hidden="true" />
          <h2 className="font-display font-bold text-xl text-brand-ink">
            Explanation
          </h2>
        </div>
        {interestCategory && (
          <span className="inline-flex items-center gap-1 bg-brand-primary/10 text-brand-primary text-xs font-sans font-semibold px-3 py-1 rounded-full">
            {interestCategory}
          </span>
        )}
      </div>

      <div className="font-sans text-sm text-brand-body leading-relaxed whitespace-pre-wrap">
        {explanationText}
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

interface VideoSectionProps {
  url: string;
  title: string;
}

function VideoSection({ url, title }: VideoSectionProps) {
  const videoId = extractYouTubeId(url);

  if (!videoId) {
    return (
      <div className="bg-white rounded-2xl border border-brand-border p-6">
        <div className="flex items-center gap-2 mb-4">
          <Play className="w-5 h-5 text-brand-primary" aria-hidden="true" />
          <h2 className="font-display font-bold text-xl text-brand-ink">
            Video
          </h2>
        </div>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-sans text-sm text-brand-primary underline hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {title}
        </a>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-brand-border p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Play className="w-5 h-5 text-brand-primary" aria-hidden="true" />
        <h2 className="font-display font-bold text-xl text-brand-ink">Video</h2>
      </div>
      <p className="font-sans text-sm text-brand-body">{title}</p>
      <div className="relative w-full" style={{ paddingTop: "56.25%" }}>
        <iframe
          src={`https://www.youtube.com/embed/${videoId}`}
          title={title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 w-full h-full rounded-xl border-0"
        />
      </div>
    </div>
  );
}

interface CheckQuestionsProps {
  questions: CourseQuestion[];
}

function CheckQuestions({ questions }: CheckQuestionsProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const answeredCount = Object.keys(answers).length;
  const allAnswered = answeredCount === questions.length;

  const correctCount = questions.filter(
    (q) => answers[q.id] === q.correct_key,
  ).length;

  const score = allAnswered ? correctCount / questions.length : null;
  const mastery = getMasteryStyle(score);

  const handleSelect = (questionId: string, key: string) => {
    if (answers[questionId]) return; // locked after answering
    setAnswers((prev) => ({ ...prev, [questionId]: key }));
  };

  return (
    <div className="bg-white rounded-2xl border border-brand-border p-6 space-y-6">
      <div className="flex items-center gap-2">
        <CheckCircle
          className="w-5 h-5 text-brand-primary"
          aria-hidden="true"
        />
        <h2 className="font-display font-bold text-xl text-brand-ink">
          Check Your Understanding
        </h2>
      </div>

      <div className="space-y-6">
        {questions.map((q, idx) => {
          const chosen = answers[q.id];
          const isCorrect = chosen === q.correct_key;

          return (
            <div key={q.id} className="space-y-3">
              <p className="font-sans font-semibold text-sm text-brand-ink">
                {idx + 1}. {q.question_text}
              </p>
              <div className="space-y-2">
                {q.options.map((opt) => {
                  const isChosen = chosen === opt.key;
                  const isCorrectOpt = opt.key === q.correct_key;
                  let optClass =
                    "w-full text-left px-4 py-3 rounded-xl border font-sans text-sm transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2";

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
                    <button
                      key={opt.key}
                      onClick={() => handleSelect(q.id, opt.key)}
                      disabled={!!chosen}
                      className={optClass}
                    >
                      <span className="font-semibold mr-2">{opt.key}.</span>
                      {opt.text}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

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
    </div>
  );
}

// ─── Page skeleton ─────────────────────────────────────────────────────────────

function MiniCourseSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-6 w-2/3 bg-brand-border rounded-full" />
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

  const { data: course, isPending, isError } = useSubtopicCourse(subtopicId!);

  const { mutate: markProgress } = useMarkCourseProgress(subtopicId!);

  const handleExplanationView = () => {
    if (!course?.progress?.explanation_accessed) {
      markProgress({ explanation_accessed: true });
    }
    setExplainOpen(true);
  };

  const handleVideoPlay = () => {
    if (!course?.progress?.video_accessed) {
      markProgress({ video_accessed: true });
    }
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
        {/* Breadcrumb + back */}
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
            {/* Page title */}
            <div className="bg-white rounded-2xl border border-brand-border p-6">
              <h1 className="font-display font-bold text-2xl text-brand-ink mb-1">
                {course.subtopic_name}
              </h1>
              <p className="font-sans text-sm text-brand-muted">
                {course.subject_name} · Grade {course.grade_level}
              </p>
            </div>

            {/* Explanation */}
            {course.explanation ? (
              <ExplanationCard
                explanationText={course.explanation.explanation_text}
                interestCategory={course.explanation.interest_category}
                contentId={course.explanation.id}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-brand-border p-8 text-center">
                <BookOpen
                  className="w-10 h-10 text-brand-muted mx-auto mb-3"
                  aria-hidden="true"
                />
                <p className="font-sans text-sm text-brand-body">
                  No explanation available for this subtopic yet.
                </p>
              </div>
            )}

            {/* Video */}
            {course.video ? (
              <div onClick={handleVideoPlay}>
                <VideoSection
                  url={course.video.url}
                  title={course.video.title}
                />
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-brand-border p-8 text-center">
                <Play
                  className="w-10 h-10 text-brand-muted mx-auto mb-3"
                  aria-hidden="true"
                />
                <p className="font-sans text-sm text-brand-body">
                  No video available for this subtopic yet.
                </p>
              </div>
            )}

            {/* Check Questions */}
            {course.questions.length > 0 ? (
              <CheckQuestions questions={course.questions} />
            ) : (
              <div className="bg-white rounded-2xl border border-brand-border p-8 text-center">
                <CheckCircle
                  className="w-10 h-10 text-brand-muted mx-auto mb-3"
                  aria-hidden="true"
                />
                <p className="font-sans text-sm text-brand-body">
                  No practice questions available yet.
                </p>
              </div>
            )}

            {/* Explain This */}
            <div className="bg-white rounded-2xl border border-brand-border p-6 flex items-center justify-between gap-4">
              <div>
                <h2 className="font-display font-bold text-lg text-brand-ink">
                  Still confused?
                </h2>
                <p className="font-sans text-sm text-brand-body mt-1">
                  Ask an AI tutor a specific question about this subtopic.
                </p>
              </div>
              <button
                onClick={handleExplanationView}
                className="flex-shrink-0 flex items-center gap-2 px-5 py-2.5 bg-brand-primary text-white rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
              >
                <MessageCircle className="w-4 h-4" aria-hidden="true" />
                Explain This
              </button>
            </div>
          </>
        ) : null}
      </div>

      {/* Explain This drawer */}
      <ExplainThisDrawer
        open={explainOpen}
        onClose={() => setExplainOpen(false)}
        subtopicId={subtopicId!}
        subtopicName={course?.subtopic_name ?? "this subtopic"}
      />
    </StudentLayout>
  );
}
