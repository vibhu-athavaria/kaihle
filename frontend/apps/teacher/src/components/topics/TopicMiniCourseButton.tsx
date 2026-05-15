import { useState, useEffect, useRef } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { useGenerateMiniCourse } from "../../hooks/useGenerateMiniCourse";

interface TopicMiniCourseButtonProps {
  topicId: string;
}

type ButtonState =
  | "idle"
  | "confirming" // brief 2-second inline note before submitting
  | "pending" // mutation in-flight
  | "generating" // pulsing badge — background work (per Rule 22)
  | "error"; // inline error for 4 seconds

export function TopicMiniCourseButton({ topicId }: TopicMiniCourseButtonProps) {
  const [uiState, setUiState] = useState<ButtonState>("idle");
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mutation = useGenerateMiniCourse();

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
      if (generateTimerRef.current) clearTimeout(generateTimerRef.current);
      if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    };
  }, []);

  function handleClick() {
    if (uiState !== "idle") return;

    // Show inline confirmation note for 2 seconds then auto-submit
    setUiState("confirming");
    confirmTimerRef.current = setTimeout(() => {
      setUiState("pending");
      mutation.mutate(topicId, {
        onSuccess: () => {
          setUiState("generating");
          // Pulsing badge persists for 5 seconds (per Rule 22 — background gen)
          generateTimerRef.current = setTimeout(() => {
            setUiState("idle");
          }, 5000);
        },
        onError: () => {
          setUiState("error");
          errorTimerRef.current = setTimeout(() => {
            setUiState("idle");
          }, 4000);
        },
      });
    }, 2000);
  }

  if (uiState === "generating") {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold text-brand-gold bg-[#fffbeb] border border-brand-gold/30 animate-pulse"
        aria-live="polite"
        aria-label="Generating mini-course content in the background"
      >
        <Sparkles className="w-3 h-3" aria-hidden="true" />
        Generating content...
      </span>
    );
  }

  if (uiState === "error") {
    return (
      <span
        className="text-xs font-medium text-red-600"
        aria-live="assertive"
        role="alert"
      >
        Generation failed. Try again.
      </span>
    );
  }

  if (uiState === "confirming") {
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
      disabled={uiState === "pending"}
      className="inline-flex items-center gap-1.5 border border-brand-gold text-brand-gold hover:bg-brand-gold hover:text-white disabled:opacity-60 disabled:cursor-not-allowed rounded-full px-4 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
      aria-label="Generate AI mini-course content for this topic"
    >
      {uiState === "pending" ? (
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
