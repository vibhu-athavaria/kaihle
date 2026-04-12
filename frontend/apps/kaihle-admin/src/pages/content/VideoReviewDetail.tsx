import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  useSubtopicContent,
  useUpdateVideoStatus,
  useAddManualVideo,
} from "../../hooks/useSubtopicContent";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { VideoReviewCard } from "../../components/content/VideoReviewCard";
import { ArrowLeft, Plus } from "lucide-react";

// ── Manual video add modal ─────────────────────────────────────────────────

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <h3 className="text-sm font-bold text-gray-900 mb-4">
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
            {isSubmitting ? "Adding..." : "Add Video"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export function VideoReviewDetail() {
  const { logout } = useAuth();
  const { subtopicId } = useParams<{ subtopicId: string }>();

  const [showAddModal, setShowAddModal] = useState(false);
  const [updatingIndex, setUpdatingIndex] = useState<number | null>(null);

  const { data, isLoading, isError } = useSubtopicContent(subtopicId ?? "");
  const updateStatus = useUpdateVideoStatus();
  const addVideo = useAddManualVideo();

  const handleApprove = async (videoIndex: number) => {
    if (!subtopicId) return;
    setUpdatingIndex(videoIndex);
    try {
      await updateStatus.mutateAsync({
        subtopicId,
        videoIndex,
        status: "approved",
      });
    } finally {
      setUpdatingIndex(null);
    }
  };

  const handleReject = async (videoIndex: number) => {
    if (!subtopicId) return;
    setUpdatingIndex(videoIndex);
    try {
      await updateStatus.mutateAsync({
        subtopicId,
        videoIndex,
        status: "rejected",
      });
    } finally {
      setUpdatingIndex(null);
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

  if (!subtopicId) {
    return (
      <AdminLayout pageTitle="Video Review" onLogout={logout}>
        <div className="p-6">
          <p className="text-sm text-red-600">Invalid subtopic ID</p>
          <Link
            to="/kaihle-admin/content/videos"
            className="text-brand-primary text-sm hover:underline mt-2 inline-block"
          >
            ← Back to Video Library
          </Link>
        </div>
      </AdminLayout>
    );
  }

  if (isLoading) {
    return (
      <AdminLayout pageTitle="Video Review" onLogout={logout}>
        <div className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-48" />
            <div className="h-4 bg-gray-200 rounded w-64" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-64 bg-gray-200 rounded-xl" />
              ))}
            </div>
          </div>
        </div>
      </AdminLayout>
    );
  }

  if (isError || !data) {
    return (
      <AdminLayout pageTitle="Video Review" onLogout={logout}>
        <div className="p-6">
          <p className="text-sm text-red-600">
            Failed to load subtopic content
          </p>
          <Link
            to="/kaihle-admin/content/videos"
            className="text-brand-primary text-sm hover:underline mt-2 inline-block"
          >
            ← Back to Video Library
          </Link>
        </div>
      </AdminLayout>
    );
  }

  const { pending_count, approved_count } = data;

  return (
    <AdminLayout pageTitle="Video Review" onLogout={logout}>
      <div className="p-6">
        {/* Back link */}
        <Link
          to="/kaihle-admin/content/videos"
          className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-brand-primary mb-4 transition-colors"
        >
          <ArrowLeft className="w-3 h-3" />
          Video Library
        </Link>

        {/* Header card */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-gray-900">
                {data.subtopic_name}
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                {data.subject_code} · Gr.{data.grade_level} ·{" "}
                {data.curriculum_code}
              </p>
              <p className="text-xs text-gray-600 mt-2 italic">
                "{data.learning_objective}"
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-xs text-gray-500">
                <span className="font-semibold text-brand-amber">
                  {pending_count}
                </span>{" "}
                pending
              </p>
              <p className="text-xs text-gray-500">
                <span className="font-semibold text-brand-primary">
                  {approved_count}
                </span>{" "}
                approved
              </p>
            </div>
          </div>
        </div>

        {/* Video grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.videos.map((video, index) => (
            <VideoReviewCard
              key={`${video.url}-${index}`}
              video={video}
              videoIndex={index}
              onApprove={handleApprove}
              onReject={handleReject}
              isUpdating={updatingIndex === index}
            />
          ))}

          {/* Add manual video card */}
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="rounded-xl border-2 border-dashed border-gray-300 hover:border-brand-primary/50 bg-gray-50 hover:bg-brand-primary/5 transition-all flex flex-col items-center justify-center min-h-[200px] gap-2 group"
          >
            <Plus className="w-8 h-8 text-gray-400 group-hover:text-brand-primary transition-colors" />
            <span className="text-xs font-medium text-gray-500 group-hover:text-brand-primary transition-colors">
              Add manual video
            </span>
          </button>
        </div>
      </div>

      {/* Add manual video modal */}
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
