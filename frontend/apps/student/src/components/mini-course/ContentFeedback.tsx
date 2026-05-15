import { useState, useRef } from "react";
import { ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";
import { useSubmitFeedback } from "../../hooks/useSubmitFeedback";

interface ContentFeedbackProps {
  contentId: string;
  subtopicId: string;
  initialFeedback?: "thumbs_up" | "thumbs_down" | null;
}

type FeedbackType = "thumbs_up" | "thumbs_down";

const MAX_COMMENT_LENGTH = 140;

export function ContentFeedback({
  contentId,
  subtopicId,
  initialFeedback = null,
}: ContentFeedbackProps) {
  const [selected, setSelected] = useState<FeedbackType | null>(
    initialFeedback ?? null,
  );
  const [pending, setPending] = useState<FeedbackType | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [showThanks, setShowThanks] = useState(false);
  const thanksTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mutation = useSubmitFeedback(contentId, subtopicId);

  function handleThumbClick(type: FeedbackType) {
    // If clicking the same thumb that's already the pending selection, deselect
    if (pending === type) {
      setPending(null);
      setComment("");
      return;
    }
    setPending(type);
    setComment("");
    setSubmitted(false);
  }

  function handleSubmit() {
    if (!pending) return;

    mutation.mutate(
      { feedback_type: pending, comment: comment.trim() || undefined },
      {
        onSuccess: () => {
          setSelected(pending);
          setPending(null);
          setComment("");
          setSubmitted(true);
          setShowThanks(true);
          if (thanksTimerRef.current) clearTimeout(thanksTimerRef.current);
          thanksTimerRef.current = setTimeout(() => setShowThanks(false), 3000);
        },
      },
    );
  }

  const isExpanded = pending !== null && !submitted;

  function thumbClasses(type: FeedbackType): string {
    const isActive =
      pending === type || (pending === null && selected === type);
    return [
      "flex items-center justify-center w-9 h-9 rounded-full transition-colors",
      "focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
      "border",
      isActive
        ? "border-brand-primary bg-brand-green-light text-brand-primary"
        : "border-brand-border bg-white text-brand-muted hover:text-brand-body hover:border-brand-body",
    ].join(" ");
  }

  return (
    <div className="mt-4">
      <p className="font-sans text-xs font-bold text-brand-muted uppercase tracking-wide mb-2">
        Was this helpful?
      </p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label="Thumbs up — helpful"
          aria-pressed={
            pending === "thumbs_up" ||
            (pending === null && selected === "thumbs_up")
          }
          className={thumbClasses("thumbs_up")}
          onClick={() => handleThumbClick("thumbs_up")}
        >
          <ThumbsUp className="w-5 h-5" aria-hidden="true" />
        </button>

        <button
          type="button"
          aria-label="Thumbs down — not helpful"
          aria-pressed={
            pending === "thumbs_down" ||
            (pending === null && selected === "thumbs_down")
          }
          className={thumbClasses("thumbs_down")}
          onClick={() => handleThumbClick("thumbs_down")}
        >
          <ThumbsDown className="w-5 h-5" aria-hidden="true" />
        </button>

        {showThanks && (
          <span className="font-sans text-xs text-brand-primary animate-pulse ml-1">
            Thanks for your feedback!
          </span>
        )}
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-2">
          <textarea
            className="w-full rounded-lg border border-brand-border bg-white px-3 py-2 font-sans text-sm text-brand-ink placeholder:text-brand-muted resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary focus:ring-offset-1"
            rows={3}
            maxLength={MAX_COMMENT_LENGTH}
            placeholder="Add a comment (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            aria-label="Optional feedback comment"
          />
          <div className="flex items-center justify-between">
            <span className="font-sans text-xs text-brand-muted">
              {comment.length}/{MAX_COMMENT_LENGTH}
            </span>
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={handleSubmit}
              className="inline-flex items-center gap-1.5 rounded-full bg-brand-primary px-4 py-1.5 font-sans text-xs font-bold text-white hover:opacity-90 disabled:opacity-60 transition-opacity focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 min-h-[36px]"
            >
              {mutation.isPending && (
                <Loader2
                  className="w-3.5 h-3.5 animate-spin"
                  aria-hidden="true"
                />
              )}
              Submit
            </button>
          </div>

          {mutation.isError && (
            <p className="font-sans text-xs text-red-600" role="alert">
              Something went wrong. Please try again.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/*
 * Usage in MiniCoursePage (T3):
 *
 * import { ContentFeedback } from "../components/mini-course/ContentFeedback";
 *
 * // Inside the explanation card, after the explanation text:
 * {course.explanation && (
 *   <ContentFeedback
 *     contentId={course.explanation.id}
 *     subtopicId={subtopicId}
 *     initialFeedback={null}
 *   />
 * )}
 */
