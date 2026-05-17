import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, BookOpen, Loader2, Sparkles } from "lucide-react";
import { useGenerateMiniCourse } from "../../hooks/useGenerateMiniCourse";
import { useCourseStatus } from "../../hooks/useCourseStatus";
import { useQueryClient } from "@tanstack/react-query";

interface TopicMiniCourseButtonProps {
  topicId: string;
  classId: string;
}

type LocalState =
  | "idle" // showing button label determined by DB status
  | "confirming" // 2-second auto-confirm before submitting
  | "pending" // mutation in-flight
  | "simulating" // pulsing badge — content existed, email queued
  | "generating" // pulsing badge — real generation running
  | "error"; // persistent red error state

export function TopicMiniCourseButton({
  topicId,
  classId,
}: TopicMiniCourseButtonProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: courseStatus, isLoading: statusLoading } =
    useCourseStatus(topicId);
  const mutation = useGenerateMiniCourse();

  const [localState, setLocalState] = useState<LocalState>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    };
  }, []);

  // When real generation completes (status flips from generating → ready),
  // return local state to idle so the "View Course" button appears.
  useEffect(() => {
    if (courseStatus?.status === "ready" && localState === "generating") {
      setLocalState("idle");
    }
    if (courseStatus?.status === "failed" && localState === "generating") {
      setLocalState("error");
      setErrorMessage("Generation failed. Our team has been notified.");
    }
  }, [courseStatus?.status, localState]);

  function handleClick() {
    if (localState !== "idle") return;
    // If already ready, go straight to Course Detail
    if (courseStatus?.status === "ready") {
      navigate(
        `/teacher/content-review/mini-courses/${topicId}?classId=${classId}`,
      );
      return;
    }

    setLocalState("confirming");
    confirmTimerRef.current = setTimeout(() => {
      setLocalState("pending");
      mutation.mutate(topicId, {
        onSuccess: (_data) => {
          // If content already existed → fast path (30s email). Show simulating badge.
          // If real generation → show generating badge and poll via useCourseStatus.
          if (courseStatus?.status === "ready") {
            setLocalState("simulating");
            // Simulating badge shows for 35s (covers the 30s email delay + buffer)
            setTimeout(() => {
              setLocalState("idle");
              queryClient.invalidateQueries({
                queryKey: ["course-status", topicId],
              });
            }, 35_000);
          } else {
            setLocalState("generating");
            // useCourseStatus polls every 5s when status = generating
            queryClient.invalidateQueries({
              queryKey: ["course-status", topicId],
            });
          }
        },
        onError: () => {
          setLocalState("error");
          setErrorMessage("Something went wrong. Please try again.");
        },
      });
    }, 2000);
  }

  if (statusLoading) {
    return <span className="text-xs text-brand-muted italic">Loading...</span>;
  }

  // Pulsing badge — simulating or real generation in progress
  if (localState === "simulating" || localState === "generating") {
    return (
      <div className="space-y-1">
        <span
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold text-brand-gold bg-[#fffbeb] border border-brand-gold/30 animate-pulse"
          aria-live="polite"
          aria-label="Generating mini-course content in the background"
        >
          <Sparkles className="w-3 h-3" aria-hidden="true" />
          Generating content...
        </span>
        <p className="text-xs text-brand-muted">
          You'll be notified by email when it's ready.
        </p>
      </div>
    );
  }

  // Persistent error state
  if (localState === "error" || courseStatus?.status === "failed") {
    return (
      <div className="space-y-1">
        <button
          type="button"
          onClick={() => {
            setLocalState("idle");
            setErrorMessage("");
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-red-600 hover:bg-red-700 transition-colors focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
          aria-label="Generation failed — click to retry"
        >
          <AlertCircle className="w-3.5 h-3.5" aria-hidden="true" />
          Generation failed — Retry
        </button>
        <p className="text-xs text-brand-muted">
          {errorMessage || "Our team has been notified. You can retry above."}
        </p>
      </div>
    );
  }

  // "View Course" — content is ready and we're in idle state
  if (courseStatus?.status === "ready" && localState === "idle") {
    return (
      <button
        type="button"
        onClick={handleClick}
        className="inline-flex items-center gap-1.5 border border-brand-primary text-brand-primary hover:bg-brand-primary hover:text-white rounded-full px-4 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        aria-label="View mini-course content for this topic"
      >
        <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
        View Course
      </button>
    );
  }

  // Default: "Generate Mini-Course" (none or failed state, idle local)
  if (localState === "confirming") {
    return (
      <span className="text-xs text-brand-muted italic" aria-live="polite">
        This will generate AI explanations for all subtopics...
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={localState === "pending"}
      className="inline-flex items-center gap-1.5 border border-brand-gold text-brand-gold hover:bg-brand-gold hover:text-white disabled:opacity-60 disabled:cursor-not-allowed rounded-full px-4 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
      aria-label="Generate AI mini-course content for this topic"
    >
      {localState === "pending" ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
          Generating...
        </>
      ) : (
        <>
          <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
          Generate Mini-Course
        </>
      )}
    </button>
  );
}
