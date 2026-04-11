import { useState } from "react";
import { CheckCircle, XCircle, ExternalLink } from "lucide-react";
import { VideoEntry } from "../../hooks/useSubtopicContent";
import { VideoStatusBadge } from "./VideoStatusBadge";

interface VideoReviewCardProps {
  video: VideoEntry;
  videoIndex: number;
  onApprove: (videoIndex: number) => void;
  onReject: (videoIndex: number) => void;
  isUpdating?: boolean;
}

export function VideoReviewCard({
  video,
  videoIndex,
  onApprove,
  onReject,
  isUpdating = false,
}: VideoReviewCardProps) {
  const [showEmbed, setShowEmbed] = useState(false);

  // Extract YouTube video ID from URL
  const getYouTubeEmbedUrl = (url: string): string | null => {
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)/,
    ];
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match && match[1]) {
        return `https://www.youtube.com/embed/${match[1]}`;
      }
    }
    return null;
  };

  const embedUrl = getYouTubeEmbedUrl(video.url);
  const isApproved = video.status === "approved";
  const isRejected = video.status === "rejected";

  return (
    <div
      className={`
        relative rounded-xl border bg-white p-4 transition-all
        ${isApproved ? "border-brand-primary/30 bg-brand-primary/5" : ""}
        ${isRejected ? "border-red-200 bg-red-50/50 opacity-60" : ""}
        ${!isApproved && !isRejected ? "border-gray-200 hover:border-gray-300" : ""}
        ${isUpdating ? "opacity-50 pointer-events-none" : ""}
      `}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-gray-900 truncate">
            {video.title}
          </h4>
          <p className="text-xs text-gray-500 mt-0.5">{video.channel}</p>
        </div>
        <VideoStatusBadge status={video.status} />
      </div>

      {/* YouTube preview */}
      {embedUrl && (
        <div className="mb-3">
          {showEmbed ? (
            <div className="relative aspect-video rounded-lg overflow-hidden bg-black">
              <iframe
                src={embedUrl}
                title={video.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                sandbox="allow-scripts allow-same-origin allow-presentation"
                className="absolute inset-0 w-full h-full"
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowEmbed(true)}
              className="w-full aspect-video rounded-lg bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors"
            >
              <div className="text-center">
                <div className="w-12 h-12 rounded-full bg-red-500 flex items-center justify-center mx-auto mb-2">
                  <svg
                    viewBox="0 0 24 24"
                    className="w-6 h-6 text-white fill-current"
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
                <span className="text-xs text-gray-500">Click to preview</span>
              </div>
            </button>
          )}
        </div>
      )}

      {/* Video metadata */}
      <div className="flex items-center gap-3 text-xs text-gray-500 mb-4">
        {video.view_count !== null && (
          <span>{video.view_count.toLocaleString()} views</span>
        )}
        <a
          href={video.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-brand-primary hover:underline"
        >
          <ExternalLink className="w-3 h-3" />
          Open on YouTube
        </a>
      </div>

      {/* Action buttons — only shown for pending videos */}
      {!isApproved && !isRejected && (
        <div className="flex items-center gap-2 pt-3 border-t border-gray-100">
          <button
            type="button"
            onClick={() => onApprove(videoIndex)}
            disabled={isUpdating}
            className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-primary text-white text-xs font-medium rounded-lg hover:bg-brand-primary/90 transition-colors disabled:opacity-50"
          >
            <CheckCircle className="w-4 h-4" />
            Approve
          </button>
          <button
            type="button"
            onClick={() => onReject(videoIndex)}
            disabled={isUpdating}
            className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-white border border-red-200 text-red-600 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <XCircle className="w-4 h-4" />
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
