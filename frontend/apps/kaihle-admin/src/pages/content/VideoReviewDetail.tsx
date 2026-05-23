import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  useSubtopicContent,
  useUpdateVideoStatus,
  useAddManualVideo,
  useRefreshVideoCandidates,
  useUpdateExplanation,
  useUpdateQuiz,
  useGenerateQuiz,
  useSubtopicExplanations,
  useUpdatePersonalisedExplanation,
  type QuizQuestionEntry,
  type ExplanationSection,
} from "../../hooks/useSubtopicContent";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { VideoReviewCard } from "../../components/content/VideoReviewCard";
import { ExplanationReviewPanel } from "../../components/content/ExplanationReviewPanel";
import { QuizReviewPanel } from "../../components/content/QuizReviewPanel";
import {
  ArrowLeft,
  Plus,
  RefreshCw,
  Video,
  BookOpen,
  HelpCircle,
  Wand2,
  Sparkles,
  Check,
  X,
} from "lucide-react";

// ── Manual video modal ─────────────────────────────────────────────────────

interface ManualVideoFormState {
  url: string;
  title: string;
  channel: string;
}

interface ManualVideoModalProps {
  onConfirm: (data: ManualVideoFormState) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

function ManualVideoModal({
  onConfirm,
  onCancel,
  isSubmitting,
}: ManualVideoModalProps) {
  const [form, setForm] = useState<ManualVideoFormState>({
    url: "",
    title: "",
    channel: "",
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="manual-video-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <h3
          id="manual-video-modal-title"
          className="text-sm font-bold text-gray-900 mb-4"
        >
          Add Manual Video
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              YouTube URL
            </label>
            <input
              type="url"
              value={form.url}
              onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
              placeholder="https://youtube.com/watch?v=..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Title
            </label>
            <input
              type="text"
              value={form.title}
              onChange={(e) =>
                setForm((f) => ({ ...f, title: e.target.value }))
              }
              placeholder="Video title"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Channel
            </label>
            <input
              type="text"
              value={form.channel}
              onChange={(e) =>
                setForm((f) => ({ ...f, channel: e.target.value }))
              }
              placeholder="Channel name"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
            />
          </div>
        </div>
        <div className="flex items-center gap-3 mt-6">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="flex-1 px-4 py-2 border border-gray-300 text-sm font-medium text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(form)}
            disabled={isSubmitting || !form.url || !form.title}
            className="flex-1 px-4 py-2 bg-brand-primary text-white text-sm font-medium rounded-lg hover:bg-brand-primary/90 disabled:opacity-50"
          >
            {isSubmitting ? "Adding…" : "Add Video"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Section wrapper ────────────────────────────────────────────────────────

function SectionCard({
  icon,
  title,
  status,
  children,
}: {
  icon: React.ReactNode;
  title: React.ReactNode;
  status: string | null | undefined;
  children: React.ReactNode;
}) {
  const statusCls =
    status === "approved"
      ? "bg-green-50 text-brand-primary border border-green-200"
      : status === "rejected"
        ? "bg-red-50 text-red-700 border border-red-200"
        : status === "pending"
          ? "bg-amber-50 text-amber-700 border border-amber-200"
          : "bg-gray-100 text-gray-500";

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          {icon}
          {title}
        </div>
        {status && (
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusCls}`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </span>
        )}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function GeneratePlaceholder({
  label,
  onGenerate,
  isGenerating,
  error,
}: {
  label: string;
  onGenerate: () => void;
  isGenerating: boolean;
  error?: string | null;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 gap-3">
      <p className="text-sm text-gray-400 italic">No {label} seeded yet.</p>
      <button
        type="button"
        onClick={onGenerate}
        disabled={isGenerating}
        className="inline-flex items-center gap-2 px-4 py-2 bg-brand-primary text-white text-xs font-medium rounded-full hover:bg-brand-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isGenerating ? (
          <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        ) : (
          <Wand2 className="w-3.5 h-3.5" />
        )}
        {isGenerating ? "Generating…" : `Generate ${label}`}
      </button>
      {error && (
        <p className="text-xs text-red-600 text-center max-w-xs">{error}</p>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export function ContentReviewDetail() {
  const { logout } = useAuth();
  const { subtopicId } = useParams<{ subtopicId: string }>();

  const [showAddModal, setShowAddModal] = useState(false);
  const [updatingVideoIndex, setUpdatingVideoIndex] = useState<number | null>(
    null,
  );

  const { data, isLoading, isError } = useSubtopicContent(subtopicId ?? "");
  const updateVideoStatus = useUpdateVideoStatus();
  const addVideo = useAddManualVideo();
  const refreshVideos = useRefreshVideoCandidates();
  const generateQuiz = useGenerateQuiz();
  const updateExplanation = useUpdateExplanation();
  const updateQuiz = useUpdateQuiz();
  const { data: explanationsData } = useSubtopicExplanations(subtopicId ?? "");
  const updatePersonalised = useUpdatePersonalisedExplanation();

  const handleApprove = async (videoIndex: number) => {
    if (!subtopicId) return;
    setUpdatingVideoIndex(videoIndex);
    try {
      await updateVideoStatus.mutateAsync({
        subtopicId,
        videoIndex,
        status: "approved",
      });
    } finally {
      setUpdatingVideoIndex(null);
    }
  };

  const handleReject = async (videoIndex: number) => {
    if (!subtopicId) return;
    setUpdatingVideoIndex(videoIndex);
    try {
      await updateVideoStatus.mutateAsync({
        subtopicId,
        videoIndex,
        status: "rejected",
      });
    } finally {
      setUpdatingVideoIndex(null);
    }
  };

  const handleAddManual = async (formData: ManualVideoFormState) => {
    if (!subtopicId) return;
    await addVideo.mutateAsync({
      subtopicId,
      payload: {
        url: formData.url,
        title: formData.title,
        channel: formData.channel || "manual",
      },
    });
    setShowAddModal(false);
  };

  const handleRefresh = async () => {
    if (!subtopicId) return;
    await refreshVideos.mutateAsync(subtopicId);
  };

  const handleSaveExplanation = async (
    text: string,
    status: "approved" | "rejected",
  ) => {
    if (!subtopicId) return;
    await updateExplanation.mutateAsync({
      subtopicId,
      payload: { explanation_text: text, review_status: status },
    });
  };

  const handleSaveQuiz = async (
    questions: QuizQuestionEntry[],
    status: "approved" | "rejected",
  ) => {
    if (!subtopicId) return;
    await updateQuiz.mutateAsync({
      subtopicId,
      payload: { questions, review_status: status },
    });
  };

  if (!subtopicId) {
    return (
      <AdminLayout pageTitle="Content Review" onLogout={logout}>
        <div className="p-6">
          <p className="text-sm text-red-600">Invalid subtopic ID</p>
          <Link
            to="/kaihle-admin/content/review"
            className="text-brand-primary text-sm hover:underline mt-2 inline-block"
          >
            ← Back
          </Link>
        </div>
      </AdminLayout>
    );
  }

  if (isLoading) {
    return (
      <AdminLayout pageTitle="Content Review" onLogout={logout}>
        <div className="p-6 space-y-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-48" />
            <div className="h-4 bg-gray-200 rounded w-64" />
            <div className="h-48 bg-gray-200 rounded-xl" />
            <div className="h-48 bg-gray-200 rounded-xl" />
            <div className="h-48 bg-gray-200 rounded-xl" />
          </div>
        </div>
      </AdminLayout>
    );
  }

  if (isError || !data) {
    return (
      <AdminLayout pageTitle="Content Review" onLogout={logout}>
        <div className="p-6">
          <p className="text-sm text-red-600">
            Failed to load content. Please refresh.
          </p>
          <Link
            to="/kaihle-admin/content/review"
            className="text-brand-primary text-sm hover:underline mt-2 inline-block"
          >
            ← Back
          </Link>
        </div>
      </AdminLayout>
    );
  }

  const isRefreshing = refreshVideos.isPending;

  return (
    <AdminLayout pageTitle="Content Review" onLogout={logout}>
      <div className="p-6 space-y-6">
        {/* Back */}
        <Link
          to="/kaihle-admin/content/review"
          className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-brand-primary transition-colors"
        >
          <ArrowLeft className="w-3 h-3" />
          Content Review
        </Link>

        {/* Subtopic header */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-gray-900">
                {data.subtopic_name}
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                {data.subject_code} · Gr.{data.grade_level} ·{" "}
                {data.curriculum_code}
              </p>
              {data.learning_objective && (
                <p className="text-xs text-gray-600 mt-2 italic max-w-xl">
                  &quot;{data.learning_objective}&quot;
                </p>
              )}
            </div>
            <div className="flex-shrink-0 flex items-center gap-3 text-xs text-gray-500">
              {data.video && (
                <span>
                  <span className="font-semibold text-brand-amber">
                    {data.video.pending_count}
                  </span>{" "}
                  vid pending
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── VIDEO SECTION ── */}
        <SectionCard
          icon={
            <Video className="w-4 h-4 text-brand-primary" aria-hidden="true" />
          }
          title="Videos"
          status={data.video?.review_status ?? null}
        >
          {!data.video ? (
            <GeneratePlaceholder
              label="videos"
              onGenerate={() => subtopicId && refreshVideos.mutate(subtopicId)}
              isGenerating={refreshVideos.isPending}
              error={
                refreshVideos.isError
                  ? ((refreshVideos.error as Error)?.message ??
                    "Failed to fetch videos")
                  : null
              }
            />
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                {data.video.videos.map((video, index) => (
                  <VideoReviewCard
                    key={`${video.url}-${index}`}
                    video={video}
                    videoIndex={index}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    isUpdating={updatingVideoIndex === index}
                  />
                ))}

                {/* Add manual video card */}
                <button
                  type="button"
                  onClick={() => setShowAddModal(true)}
                  className="rounded-xl border-2 border-dashed border-gray-300 hover:border-brand-primary/50 bg-gray-50 hover:bg-brand-primary/5 transition-all flex flex-col items-center justify-center min-h-[160px] gap-2 group"
                >
                  <Plus className="w-7 h-7 text-gray-400 group-hover:text-brand-primary transition-colors" />
                  <span className="text-xs font-medium text-gray-500 group-hover:text-brand-primary transition-colors">
                    Add manual video
                  </span>
                </button>
              </div>

              {/* Fetch more button */}
              <div className="pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand-primary transition-colors disabled:opacity-50"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`}
                  />
                  {isRefreshing
                    ? "Searching YouTube…"
                    : "Fetch more candidates"}
                </button>
                {refreshVideos.isError && (
                  <p className="mt-1 text-xs text-red-600">
                    {(refreshVideos.error as Error)?.message ??
                      "No new candidates found."}
                  </p>
                )}
              </div>
            </>
          )}
        </SectionCard>

        {/* ── EXPLANATION SECTION ── */}
        <SectionCard
          icon={
            <BookOpen
              className="w-4 h-4 text-brand-primary"
              aria-hidden="true"
            />
          }
          title="Explanation"
          status={data.explanation?.review_status ?? null}
        >
          {!data.explanation ? (
            <p className="text-sm text-gray-400 italic text-center py-6">
              No explanation seeded yet. Run the seed script to generate one.
            </p>
          ) : (
            <ExplanationReviewPanel
              explanation={data.explanation}
              onSave={handleSaveExplanation}
              isSaving={updateExplanation.isPending}
            />
          )}
        </SectionCard>

        {/* ── PERSONALISED EXPLANATIONS ── */}
        {explanationsData && explanationsData.personalised.length > 0 && (
          <SectionCard
            icon={
              <Sparkles
                className="w-4 h-4 text-brand-primary"
                aria-hidden="true"
              />
            }
            title={
              <span className="flex items-center gap-2">
                Personalised Explanations
                {explanationsData.personalised.filter(
                  (e) => e.review_status === "pending",
                ).length > 0 && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-700">
                    {
                      explanationsData.personalised.filter(
                        (e) => e.review_status === "pending",
                      ).length
                    }{" "}
                    pending
                  </span>
                )}
              </span>
            }
            status={null}
          >
            <div className="space-y-4">
              {explanationsData.personalised.map((exp: ExplanationSection) => (
                <div
                  key={exp.content_id}
                  className="border border-role-admin-border rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-['Inter'] text-xs font-semibold text-role-admin-ink capitalize">
                      {exp.content_id}
                    </span>
                    <span
                      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        exp.review_status === "approved"
                          ? "bg-green-50 text-brand-primary border border-green-200"
                          : exp.review_status === "rejected"
                            ? "bg-red-50 text-red-700 border border-red-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {exp.review_status}
                    </span>
                  </div>
                  <p className="font-['Inter'] text-xs text-role-admin-subtle leading-relaxed whitespace-pre-wrap">
                    {exp.explanation_text ?? <em>No text yet.</em>}
                  </p>
                  {exp.review_status === "pending" && subtopicId && (
                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          updatePersonalised.mutate({
                            subtopicId,
                            payload: {
                              explanation_text: exp.explanation_text ?? "",
                              review_status: "approved",
                            },
                          })
                        }
                        disabled={updatePersonalised.isPending}
                        className="inline-flex items-center gap-1.5 bg-brand-primary text-white rounded-full px-3 py-1.5 text-xs font-['Inter'] font-semibold hover:opacity-90 disabled:opacity-50"
                      >
                        <Check className="w-3 h-3" aria-hidden="true" />
                        Approve
                      </button>
                      <button
                        onClick={() =>
                          updatePersonalised.mutate({
                            subtopicId,
                            payload: {
                              explanation_text: exp.explanation_text ?? "",
                              review_status: "rejected",
                            },
                          })
                        }
                        disabled={updatePersonalised.isPending}
                        className="inline-flex items-center gap-1.5 border border-red-300 text-red-600 rounded-full px-3 py-1.5 text-xs font-['Inter'] font-semibold hover:bg-red-50 disabled:opacity-50"
                      >
                        <X className="w-3 h-3" aria-hidden="true" />
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        {/* ── QUIZ SECTION ── */}
        <SectionCard
          icon={
            <HelpCircle
              className="w-4 h-4 text-brand-primary"
              aria-hidden="true"
            />
          }
          title={
            <span className="flex items-center gap-3">
              Practice Quiz
              {data.quiz && (
                <button
                  type="button"
                  onClick={() => subtopicId && generateQuiz.mutate(subtopicId)}
                  disabled={generateQuiz.isPending}
                  className="inline-flex items-center gap-1 text-[10px] font-medium text-gray-400 hover:text-brand-primary transition-colors disabled:opacity-50"
                >
                  <RefreshCw
                    className={`w-3 h-3 ${generateQuiz.isPending ? "animate-spin" : ""}`}
                  />
                  Regenerate
                </button>
              )}
            </span>
          }
          status={data.quiz?.review_status ?? null}
        >
          {!data.quiz ? (
            <GeneratePlaceholder
              label="quiz"
              onGenerate={() => subtopicId && generateQuiz.mutate(subtopicId)}
              isGenerating={generateQuiz.isPending}
              error={
                generateQuiz.isError
                  ? ((generateQuiz.error as Error)?.message ??
                    "Failed to generate quiz")
                  : null
              }
            />
          ) : (
            <QuizReviewPanel
              quiz={data.quiz}
              onSave={handleSaveQuiz}
              isSaving={updateQuiz.isPending}
            />
          )}
        </SectionCard>
      </div>

      {showAddModal && (
        <ManualVideoModal
          onConfirm={handleAddManual}
          onCancel={() => setShowAddModal(false)}
          isSubmitting={addVideo.isPending}
        />
      )}
    </AdminLayout>
  );
}
