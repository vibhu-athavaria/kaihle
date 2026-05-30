import { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import {
  ChevronLeft,
  Edit3,
  Loader2,
  CheckCircle,
  XCircle,
  Lock,
} from "lucide-react";
import { useClass } from "../hooks/useClass";
import {
  useSubtopicContentStatus,
  useSubtopicExplanations,
  useSubtopicVideos,
  useSubtopicVideoCandidates,
  useTeacherApproveContent,
  useTeacherQuizQuestions,
  useSelectVideo,
  useSuggestVideo,
  useSubmitExplanationSuggestion,
  type PersonalisedExplanation,
  type ContentStatus,
  type QuizQuestion,
  type VideoCandidateEntry,
} from "../hooks/useSubtopicContent";
import { Badge, Button, EmptyState, Skeleton, toast } from "@kaihle/ui";

type TabId = "video" | "explanation" | "quiz";

const TABS: { id: TabId; label: string }[] = [
  { id: "video", label: "Videos" },
  { id: "explanation", label: "Explanation" },
  { id: "quiz", label: "Quiz" },
];

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "approved":
      return <Badge variant="success">Approved</Badge>;
    case "pending":
      return <Badge variant="gold">Pending</Badge>;
    case "rejected":
      return <Badge variant="danger">Rejected</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

function ContentStatusBadge({ status }: { status: ContentStatus }) {
  switch (status) {
    case "approved":
      return <Badge variant="success">Approved</Badge>;
    case "own_school_pending":
      return <Badge variant="gold">Pending your approval</Badge>;
    case "other_school_pending":
      return <Badge variant="neutral">Pending platform review</Badge>;
    case "curriculum_pending":
      return <Badge variant="neutral">Under platform review</Badge>;
    case "rejected":
      return <Badge variant="danger">Rejected</Badge>;
    default:
      return null;
  }
}

// ── Suggest Edit slide-out panel ────────────────────────────────────────────

function SuggestEditPanel({
  contentId,
  originalText,
  label,
  onClose,
}: {
  contentId: string;
  originalText: string;
  label: string;
  onClose: () => void;
}) {
  const [text, setText] = useState(originalText);
  const suggest = useSubmitExplanationSuggestion();

  function handleSubmit() {
    if (!text.trim() || text.trim() === originalText.trim()) return;
    suggest.mutate(
      { contentId, suggestedText: text.trim() },
      {
        onSuccess: () => {
          toast.success("Suggestion submitted for admin review.");
          onClose();
        },
        onError: () => toast.error("Failed to submit suggestion."),
      },
    );
  }

  const isDirty =
    text.trim() !== originalText.trim() && text.trim().length >= 10;

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-white border-l border-brand-border shadow-xl flex flex-col z-50">
      <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
        <div>
          <p className="text-sm font-bold text-brand-ink">Suggest Edit</p>
          <p className="text-xs text-brand-muted truncate max-w-xs">{label}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-brand-muted hover:text-brand-ink transition-colors"
          aria-label="Close panel"
        >
          <XCircle className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        <div>
          <p className="text-xs font-bold text-brand-muted uppercase tracking-wide mb-2">
            Original
          </p>
          <div className="bg-brand-surface rounded-lg p-3 text-sm text-brand-body leading-relaxed whitespace-pre-wrap">
            {originalText}
          </div>
        </div>

        <div>
          <p className="text-xs font-bold text-brand-muted uppercase tracking-wide mb-2">
            Your suggestion
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            disabled={suggest.isPending}
            className="w-full border border-brand-border rounded-lg px-3 py-2.5 text-sm text-brand-ink leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-primary/30 resize-y disabled:opacity-50"
            placeholder="Edit the explanation text…"
          />
          <p className="text-xs text-brand-muted mt-1">
            {text.trim().length} characters
            {text.trim().length < 10 ? " — minimum 10 required" : ""}
          </p>
        </div>
      </div>

      <div className="px-5 py-4 border-t border-brand-border flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          disabled={!isDirty || suggest.isPending}
          onClick={handleSubmit}
          className="gap-1"
        >
          {suggest.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
          )}
          {suggest.isPending ? "Submitting…" : "Submit suggestion"}
        </Button>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

// ── Explanation tab ─────────────────────────────────────────────────────────

function ExplanationTab({
  subtopicId,
  videoStatus,
  explanationStatus,
}: {
  subtopicId: string;
  videoStatus: ContentStatus;
  explanationStatus: ContentStatus;
}) {
  const { data, isLoading, isError } = useSubtopicExplanations(subtopicId);
  const approveContent = useTeacherApproveContent();
  const [suggestionPanel, setSuggestionPanel] = useState<{
    contentId: string;
    text: string;
    label: string;
  } | null>(null);

  void videoStatus;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        emoji="⚠️"
        title="Failed to load explanations"
        description="Please refresh the page and try again."
      />
    );
  }

  function handleApprove(contentType: "explanation") {
    approveContent.mutate(
      { subtopicId, contentType, action: "approve" },
      {
        onSuccess: () => toast.success("Content approved."),
        onError: () => toast.error("Approval failed."),
      },
    );
  }

  function handleReject(contentType: "explanation") {
    approveContent.mutate(
      { subtopicId, contentType, action: "reject" },
      {
        onSuccess: () => toast.success("Content rejected."),
        onError: () => toast.error("Rejection failed."),
      },
    );
  }

  const canApproveOwn = explanationStatus === "own_school_pending";

  return (
    <>
      <div className="space-y-5">
        {/* Generic explanation */}
        <div>
          <h3 className="font-semibold text-brand-ink text-sm mb-3">
            Generic Explanation
          </h3>
          {data.generic ? (
            <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <StatusBadge status={data.generic.review_status} />
                {data.generic.explanation_text && (
                  <button
                    type="button"
                    onClick={() =>
                      setSuggestionPanel({
                        contentId: data.generic!.content_id,
                        text: data.generic!.explanation_text ?? "",
                        label: "Generic explanation",
                      })
                    }
                    className="inline-flex items-center gap-1 text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
                  >
                    <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
                    Suggest Edit
                  </button>
                )}
              </div>
              {data.generic.explanation_text ? (
                <p className="text-sm text-brand-body leading-relaxed whitespace-pre-wrap">
                  {data.generic.explanation_text}
                </p>
              ) : (
                <p className="text-sm text-brand-muted italic">
                  No explanation text yet.
                </p>
              )}
              {canApproveOwn && (
                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-brand-border">
                  <Button
                    variant="primary"
                    size="sm"
                    className="gap-1"
                    onClick={() => handleApprove("explanation")}
                    disabled={approveContent.isPending}
                  >
                    {approveContent.isPending ? (
                      <Loader2
                        className="w-3.5 h-3.5 animate-spin"
                        aria-hidden="true"
                      />
                    ) : (
                      <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />
                    )}
                    Approve
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="gap-1"
                    onClick={() => handleReject("explanation")}
                    disabled={approveContent.isPending}
                  >
                    <XCircle className="w-3.5 h-3.5" aria-hidden="true" />
                    Reject
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-brand-muted italic">
              No generic explanation generated yet.
            </p>
          )}
        </div>

        {/* Personalised explanations */}
        {data.personalised.length > 0 && (
          <div>
            <h3 className="font-semibold text-brand-ink text-sm mb-3">
              Personalised Explanations
            </h3>
            <div className="space-y-3">
              {data.personalised.map((item: PersonalisedExplanation) => (
                <div
                  key={item.content_id}
                  className="bg-white border border-brand-border rounded-xl p-5 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-brand-muted uppercase tracking-wide">
                        {item.interest_category_name}
                      </span>
                      <StatusBadge status={item.review_status} />
                    </div>
                    {item.explanation_text && (
                      <button
                        type="button"
                        onClick={() =>
                          setSuggestionPanel({
                            contentId: item.content_id,
                            text: item.explanation_text ?? "",
                            label: `${item.interest_category_name} explanation`,
                          })
                        }
                        className="inline-flex items-center gap-1 text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
                      >
                        <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
                        Suggest Edit
                      </button>
                    )}
                  </div>
                  {item.explanation_text ? (
                    <p className="text-sm text-brand-body leading-relaxed whitespace-pre-wrap">
                      {item.explanation_text}
                    </p>
                  ) : (
                    <p className="text-sm text-brand-muted italic">
                      Generating…
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Slide-out suggestion panel */}
      {suggestionPanel && (
        <>
          <div
            className="fixed inset-0 bg-black/20 z-40"
            onClick={() => setSuggestionPanel(null)}
            aria-hidden="true"
          />
          <SuggestEditPanel
            contentId={suggestionPanel.contentId}
            originalText={suggestionPanel.text}
            label={suggestionPanel.label}
            onClose={() => setSuggestionPanel(null)}
          />
        </>
      )}
    </>
  );
}

// ── Video tab ───────────────────────────────────────────────────────────────

// YouTube video IDs are strictly alphanumeric + hyphen + underscore (11 chars).
// Validate after extraction to prevent an adversarial URL injecting content into
// the embed src (e.g. a crafted v= param containing path traversal or JS).
const YOUTUBE_ID_RE = /^[A-Za-z0-9_-]{1,20}$/;

function getYouTubeId(url: string): string | null {
  try {
    const u = new URL(url);
    const id = u.hostname.includes("youtu.be")
      ? u.pathname.slice(1).split("/")[0]
      : u.searchParams.get("v");
    if (id && YOUTUBE_ID_RE.test(id)) return id;
    return null;
  } catch {
    return null;
  }
}

function VideoCard({
  url,
  title,
  channel,
}: {
  url: string;
  title: string;
  channel: string;
}) {
  const videoId = getYouTubeId(url);
  return (
    <div className="bg-white border border-brand-border rounded-xl overflow-hidden shadow-sm">
      {videoId ? (
        <div className="aspect-video w-full">
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            title={title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="w-full h-full"
          />
        </div>
      ) : (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-4 text-brand-primary underline text-sm truncate"
        >
          {url}
        </a>
      )}
      <div className="px-4 py-3">
        <p className="text-sm font-semibold text-brand-ink leading-snug line-clamp-2">
          {title}
        </p>
        <p className="text-xs text-brand-muted mt-0.5">{channel}</p>
      </div>
    </div>
  );
}

function GeneratingPlaceholder({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-brand-gold/10 border border-amber-200 rounded-lg w-fit">
      <Loader2
        className="w-3.5 h-3.5 animate-spin text-brand-gold"
        aria-hidden="true"
      />
      <span className="text-xs font-medium text-brand-gold-dark">{label}</span>
    </div>
  );
}

// ── Selectable video candidate card (own-school view) ───────────────────────

function VideoCandidateCard({
  video,
  index,
  isSelected,
  onSelect,
  isSelecting,
}: {
  video: VideoCandidateEntry;
  index: number;
  isSelected: boolean;
  onSelect: (index: number) => void;
  isSelecting: boolean;
}) {
  const videoId = getYouTubeId(video.url);
  return (
    <div
      className={[
        "rounded-xl overflow-hidden border-2 shadow-sm transition-colors",
        isSelected
          ? "border-brand-gold"
          : "border-brand-border hover:border-brand-gold/40",
      ].join(" ")}
    >
      {videoId ? (
        <div className="aspect-video w-full">
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            title={video.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="w-full h-full"
          />
        </div>
      ) : (
        <a
          href={video.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-4 text-brand-primary underline text-sm truncate"
        >
          {video.url}
        </a>
      )}
      <div className="px-4 py-3 bg-white flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-brand-ink leading-snug line-clamp-2">
            {video.title}
          </p>
          <p className="text-xs text-brand-muted mt-0.5">{video.channel}</p>
        </div>
        <button
          type="button"
          disabled={isSelecting}
          onClick={() => onSelect(index)}
          className={[
            "flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold transition-colors disabled:opacity-50",
            isSelected
              ? "bg-brand-gold text-white"
              : "border border-brand-gold text-brand-gold hover:bg-brand-gold hover:text-white",
          ].join(" ")}
          aria-pressed={isSelected}
        >
          {isSelecting && !isSelected ? (
            <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
          ) : (
            <CheckCircle className="w-3 h-3" aria-hidden="true" />
          )}
          {isSelected ? "Selected" : "Select"}
        </button>
      </div>
    </div>
  );
}

// ── Suggest video panel (other-school teachers) ─────────────────────────────

function SuggestVideoPanel({
  subtopicId,
  onClose,
}: {
  subtopicId: string;
  onClose: () => void;
}) {
  const [message, setMessage] = useState("");
  const suggest = useSuggestVideo();

  return (
    <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm space-y-3">
      <p className="text-sm font-semibold text-brand-ink">
        Suggest a different video
      </p>
      <p className="text-xs text-brand-muted">
        Describe what you&apos;d like changed — Kaihle admins will review your
        request.
      </p>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={4}
        placeholder="e.g. The current video is too advanced for Grade 8. Could you find one that covers the basics first?"
        className="w-full border border-brand-border rounded-lg px-3 py-2.5 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-gold/30 resize-y"
      />
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          disabled={message.trim().length < 10 || suggest.isPending}
          onClick={() =>
            suggest.mutate(
              { subtopicId, message: message.trim() },
              {
                onSuccess: () => {
                  toast.success("Suggestion submitted to Kaihle admins.");
                  onClose();
                },
                onError: () => toast.error("Failed to submit suggestion."),
              },
            )
          }
        >
          {suggest.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
          ) : null}
          Submit suggestion
        </Button>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function VideoTab({
  status,
  scope,
  subtopicId,
}: {
  status: ContentStatus;
  scope: "curriculum" | "school" | null;
  subtopicId: string;
}) {
  const approveContent = useTeacherApproveContent();
  const selectVideo = useSelectVideo();
  const [showSuggest, setShowSuggest] = useState(false);

  // scope="school" means this teacher's school generated the content — they see
  // all 3 candidates and can switch selection freely until KaihleAdmin promotes.
  // Any other scope means they see only the approved video + a suggest CTA.
  const isOwnSchool = scope === "school";

  const { data: candidates, isLoading: candidatesLoading } =
    useSubtopicVideoCandidates(isOwnSchool ? subtopicId : undefined);
  const { data: approvedVideos, isLoading: approvedLoading } =
    useSubtopicVideos(
      !isOwnSchool && status !== "none" ? subtopicId : undefined,
    );

  if (status === "none") {
    return (
      <EmptyState
        emoji="🎬"
        title="No videos yet"
        description="Use the card on the class page to request video generation."
      />
    );
  }

  // ── Own-school view: all 3 candidates with radio-select ─────────────────
  if (isOwnSchool) {
    const hasCandidates = candidates && candidates.length > 0;
    return (
      <div className="space-y-4">
        <div className="bg-white border border-brand-border rounded-xl p-4 shadow-sm flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-brand-ink">
              {candidates?.some((v) => v.status === "approved")
                ? "Video selected — students see the highlighted one."
                : "Select a video for students."}
            </p>
            <p className="text-xs text-brand-muted mt-0.5">
              You can switch your selection any time before the platform
              promotes it globally.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              approveContent.mutate(
                { subtopicId, contentType: "video", action: "reject" },
                {
                  onSuccess: () =>
                    toast.success(
                      "Videos rejected. You can generate new ones.",
                    ),
                  onError: () => toast.error("Failed to reject."),
                },
              )
            }
            disabled={approveContent.isPending}
          >
            <XCircle className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
            Reject all
          </Button>
        </div>

        {candidatesLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-xl overflow-hidden border border-brand-border"
              >
                <div className="aspect-video bg-gray-100" />
                <div className="p-4 space-y-2">
                  <div className="h-4 bg-gray-100 rounded w-3/4" />
                  <div className="h-3 bg-gray-100 rounded w-1/4" />
                </div>
              </div>
            ))}
          </div>
        ) : !hasCandidates ? (
          <GeneratingPlaceholder label="Searching for video candidates…" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {candidates.map((v, i) => (
              <VideoCandidateCard
                key={i}
                video={v}
                index={i}
                isSelected={v.status === "approved"}
                isSelecting={selectVideo.isPending}
                onSelect={(idx) =>
                  selectVideo.mutate(
                    { subtopicId, videoIndex: idx },
                    {
                      onSuccess: () => toast.success("Video selected."),
                      onError: () => toast.error("Selection failed."),
                    },
                  )
                }
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Other-school / curriculum view: approved video + lock banner ────────
  const isCurriculumLocked = scope === "curriculum";

  return (
    <div className="space-y-4">
      {isCurriculumLocked ? (
        <div className="flex items-start gap-3 px-4 py-3 bg-brand-border/30 border border-brand-border rounded-xl">
          <Lock
            className="w-4 h-4 text-brand-muted flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-brand-ink">
              Managed by the Kaihle platform
            </p>
            <p className="text-xs text-brand-muted mt-0.5">
              This video has been approved globally and can no longer be
              switched by teachers. Use the suggestion form below if you&apos;d
              like a change.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <ContentStatusBadge status={status} />
          </div>
          {status !== "approved" && (
            <p className="text-sm text-brand-muted">
              {status === "curriculum_pending"
                ? "Video is being reviewed by the Kaihle platform team."
                : status === "rejected"
                  ? "Video was rejected."
                  : "Video is pending review."}
            </p>
          )}
        </div>
      )}

      {!showSuggest && (
        <button
          type="button"
          onClick={() => setShowSuggest(true)}
          className="text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
        >
          Suggest a different video
        </button>
      )}

      {showSuggest && (
        <SuggestVideoPanel
          subtopicId={subtopicId}
          onClose={() => setShowSuggest(false)}
        />
      )}

      {approvedLoading ? (
        <div className="animate-pulse rounded-xl overflow-hidden border border-brand-border">
          <div className="aspect-video bg-gray-100" />
          <div className="p-4 space-y-2">
            <div className="h-4 bg-gray-100 rounded w-3/4" />
            <div className="h-3 bg-gray-100 rounded w-1/4" />
          </div>
        </div>
      ) : approvedVideos && approvedVideos.length > 0 ? (
        <VideoCard
          url={approvedVideos[0].url}
          title={approvedVideos[0].title}
          channel={approvedVideos[0].channel}
        />
      ) : null}
    </div>
  );
}

// ── Quiz tab ────────────────────────────────────────────────────────────────

function QuizQuestionCard({ q, index }: { q: QuizQuestion; index: number }) {
  return (
    <div className="bg-white border border-brand-border rounded-xl p-4 shadow-sm space-y-3">
      <div className="flex items-start gap-2">
        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-gold/15 text-brand-gold-dark text-xs font-bold flex items-center justify-center mt-0.5">
          {index + 1}
        </span>
        <p className="text-sm font-medium text-brand-ink leading-snug">
          {q.question_text}
        </p>
      </div>
      <ul className="space-y-1.5 pl-7">
        {q.options.map((opt) => (
          <li
            key={opt}
            className={[
              "text-sm px-2.5 py-1.5 rounded-lg",
              opt.startsWith(q.correct_answer)
                ? "bg-brand-green-light text-brand-green font-semibold"
                : "text-brand-body",
            ].join(" ")}
          >
            {opt}
          </li>
        ))}
      </ul>
      {q.explanation && (
        <p className="pl-7 text-xs text-brand-muted italic">{q.explanation}</p>
      )}
    </div>
  );
}

function QuizTab({
  status,
  subtopicId,
}: {
  status: ContentStatus;
  subtopicId: string;
}) {
  const approveContent = useTeacherApproveContent();
  const { data: quizData, isLoading: quizLoading } = useTeacherQuizQuestions(
    status !== "none" ? subtopicId : undefined,
  );

  if (status === "none") {
    return (
      <EmptyState
        emoji="❓"
        title="No quiz yet"
        description="Use the card on the class page to request quiz generation."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <ContentStatusBadge status={status} />
          {status === "own_school_pending" && (
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                className="gap-1"
                onClick={() =>
                  approveContent.mutate(
                    { subtopicId, contentType: "quiz", action: "approve" },
                    {
                      onSuccess: () => toast.success("Quiz approved."),
                      onError: () => toast.error("Approval failed."),
                    },
                  )
                }
                disabled={approveContent.isPending}
              >
                {approveContent.isPending ? (
                  <Loader2
                    className="w-3.5 h-3.5 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />
                )}
                Approve
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  approveContent.mutate(
                    { subtopicId, contentType: "quiz", action: "reject" },
                    {
                      onSuccess: () => toast.success("Quiz rejected."),
                      onError: () => toast.error("Rejection failed."),
                    },
                  )
                }
                disabled={approveContent.isPending}
              >
                Reject
              </Button>
            </div>
          )}
        </div>
        <p className="text-sm text-brand-muted mt-2">
          {status === "approved"
            ? "Quiz has been approved and is available to students."
            : status === "curriculum_pending" ||
                status === "other_school_pending"
              ? "Quiz is being reviewed by the Kaihle platform team."
              : status === "rejected"
                ? "Quiz was rejected. Generate a new one from the class page."
                : "Review the questions below, then approve or reject."}
        </p>
      </div>

      {/* Questions list */}
      {quizLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : quizData && quizData.questions.length > 0 ? (
        <div className="space-y-3">
          {quizData.questions.map((q, i) => (
            <QuizQuestionCard key={q.question_id || i} q={q} index={i} />
          ))}
        </div>
      ) : status === "own_school_pending" ? (
        <GeneratingPlaceholder label="Generating quiz questions…" />
      ) : null}
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export function SubtopicContentBrowser() {
  const { classId, subtopicId } = useParams<{
    classId: string;
    subtopicId: string;
  }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: cls } = useClass(classId);
  const { data: statusData, isLoading: statusLoading } =
    useSubtopicContentStatus(subtopicId ?? "");

  const activeTab = (searchParams.get("tab") as TabId) ?? "explanation";

  function setTab(tab: TabId) {
    setSearchParams({ tab });
  }

  if (!classId || !subtopicId) {
    return (
      <div className="text-center py-12 text-brand-muted">
        Missing route parameters.
      </div>
    );
  }

  return (
    <div className="space-y-5 p-6">
      {/* Breadcrumb */}
      <nav
        className="flex items-center gap-2 text-sm text-brand-muted"
        aria-label="Breadcrumb"
      >
        <Link
          to="/teacher/classes"
          className="hover:text-brand-ink transition-colors"
        >
          Classes
        </Link>
        <span className="text-brand-border" aria-hidden="true">
          /
        </span>
        <Link
          to={`/teacher/classes/${classId}`}
          className="hover:text-brand-ink transition-colors"
        >
          {cls?.name ?? "Class"}
        </Link>
        <span className="text-brand-border" aria-hidden="true">
          /
        </span>
        <span className="text-brand-ink font-medium">Content</span>
      </nav>

      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to={`/teacher/classes/${classId}`}
          className="p-1.5 hover:bg-brand-surface rounded-lg transition-colors"
          aria-label="Back to class"
        >
          <ChevronLeft className="w-5 h-5 text-brand-muted" />
        </Link>
        <div>
          <h1 className="font-display font-bold text-xl text-brand-ink">
            Subtopic Content
          </h1>
          <p className="text-xs text-brand-muted">
            Review and manage content for this subtopic
          </p>
        </div>
      </div>

      {/* Tab bar */}
      <div
        className="flex gap-0 border-b border-brand-border"
        role="tablist"
        aria-label="Content types"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            aria-selected={activeTab === id}
            onClick={() => setTab(id)}
            className={[
              "px-4 py-3 font-sans text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded-t",
              activeTab === id
                ? "text-brand-gold border-b-2 border-brand-gold -mb-px"
                : "text-brand-body hover:text-brand-ink",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {statusLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : statusData ? (
        <>
          {activeTab === "video" && (
            <VideoTab
              status={statusData.video.status}
              scope={statusData.video.scope}
              subtopicId={subtopicId}
            />
          )}
          {activeTab === "explanation" && (
            <ExplanationTab
              subtopicId={subtopicId}
              videoStatus={statusData.video.status}
              explanationStatus={statusData.explanation.status}
            />
          )}
          {activeTab === "quiz" && (
            <QuizTab status={statusData.quiz.status} subtopicId={subtopicId} />
          )}
        </>
      ) : (
        <EmptyState
          emoji="⚠️"
          title="Could not load content status"
          description="Please refresh the page."
        />
      )}
    </div>
  );
}
