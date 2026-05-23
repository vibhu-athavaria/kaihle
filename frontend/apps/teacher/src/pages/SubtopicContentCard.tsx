import { Link } from "react-router-dom";
import { Loader2, Video, BookOpen, HelpCircle } from "lucide-react";
import {
  useSubtopicContentStatus,
  type ContentStatus,
} from "../hooks/useSubtopicContent";
import { useTeacherGenerateContent } from "../hooks/useSubtopicContent";
import { toast } from "@kaihle/ui";

interface SubtopicContentCardProps {
  subtopicId: string;
  classId: string;
  subtopicName: string;
}

type ContentTypeKey = "video" | "explanation" | "quiz";

const CONTENT_TYPES: {
  key: ContentTypeKey;
  label: string;
  icon: React.ElementType;
}[] = [
  { key: "video", label: "Videos", icon: Video },
  { key: "explanation", label: "Explanation", icon: BookOpen },
  { key: "quiz", label: "Quiz", icon: HelpCircle },
];

function statusBadgeClass(status: ContentStatus): string {
  switch (status) {
    case "approved":
      return "bg-brand-green-light text-brand-green border-brand-green/20";
    case "own_school_pending":
      return "bg-[#fffbeb] text-brand-gold-dark border-amber-200";
    case "curriculum_pending":
    case "other_school_pending":
      return "bg-gray-50 text-brand-muted border-brand-border";
    case "rejected":
      return "bg-red-50 text-red-600 border-red-100";
    default:
      return "bg-gray-50 text-brand-muted border-brand-border";
  }
}

function statusLabel(status: ContentStatus): string {
  switch (status) {
    case "approved":
      return "Approved";
    case "own_school_pending":
      return "Pending approval";
    case "other_school_pending":
      return "Platform review";
    case "curriculum_pending":
      return "Under review";
    case "rejected":
      return "Rejected";
    default:
      return "None";
  }
}

function ContentTypeColumn({
  typeKey,
  label,
  icon: Icon,
  status,
  subtopicId,
  classId,
  isGenerating,
  onGenerate,
}: {
  typeKey: ContentTypeKey;
  label: string;
  icon: React.ElementType;
  status: ContentStatus;
  subtopicId: string;
  classId: string;
  isGenerating: boolean;
  onGenerate: (type: ContentTypeKey) => void;
}) {
  const browseUrl = `/teacher/classes/${classId}/subtopics/${subtopicId}/content?tab=${typeKey}`;

  return (
    <div className="flex flex-col items-start gap-1.5 min-w-0">
      <div className="flex items-center gap-1 text-xs font-bold text-brand-muted uppercase tracking-wide">
        <Icon className="w-3 h-3" aria-hidden="true" />
        {label}
      </div>

      {status === "none" ? (
        <button
          type="button"
          disabled={isGenerating}
          onClick={() => onGenerate(typeKey)}
          className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-gold text-white text-xs font-semibold rounded-full hover:bg-brand-gold-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
          ) : null}
          {isGenerating ? "Generating…" : "Generate"}
        </button>
      ) : status === "rejected" ? (
        <button
          type="button"
          disabled={isGenerating}
          onClick={() => onGenerate(typeKey)}
          className="inline-flex items-center gap-1 px-2.5 py-1 border border-brand-gold text-brand-gold text-xs font-semibold rounded-full hover:bg-[#fffbeb] transition-colors disabled:opacity-50"
        >
          {isGenerating ? (
            <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
          ) : null}
          Regenerate
        </button>
      ) : (
        <div className="flex flex-col gap-1">
          <span
            className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full border ${statusBadgeClass(status)}`}
          >
            {statusLabel(status)}
          </span>
          <Link
            to={browseUrl}
            className="text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
          >
            {status === "own_school_pending" ? "Review →" : "View →"}
          </Link>
        </div>
      )}
    </div>
  );
}

export function SubtopicContentCard({
  subtopicId,
  classId,
  subtopicName,
}: SubtopicContentCardProps) {
  const { data, isLoading, isError } = useSubtopicContentStatus(subtopicId);
  const generate = useTeacherGenerateContent();

  function handleGenerate(contentType: ContentTypeKey) {
    generate.mutate(
      { subtopicId, contentType },
      {
        onSuccess: () =>
          toast.success(
            `${contentType.charAt(0).toUpperCase() + contentType.slice(1)} generation requested.`,
          ),
        onError: () => toast.error("Generation request failed."),
      },
    );
  }

  if (isLoading) {
    return (
      <div className="bg-white border border-brand-border rounded-lg p-3 animate-pulse">
        <div className="h-3 w-2/3 bg-gray-100 rounded mb-3" />
        <div className="flex gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 w-20 bg-gray-100 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="bg-white border border-brand-border rounded-lg p-3 text-xs text-brand-muted">
        Could not load content status for {subtopicName}.
      </div>
    );
  }

  return (
    <div className="bg-white border border-brand-border rounded-lg p-3">
      <p className="text-xs font-semibold text-brand-ink mb-2.5 truncate">
        {subtopicName}
      </p>
      <div className="flex gap-5">
        {CONTENT_TYPES.map(({ key, label, icon }) => (
          <ContentTypeColumn
            key={key}
            typeKey={key}
            label={label}
            icon={icon}
            status={data[key].status}
            subtopicId={subtopicId}
            classId={classId}
            isGenerating={
              generate.isPending &&
              generate.variables?.subtopicId === subtopicId &&
              generate.variables?.contentType === key
            }
            onGenerate={handleGenerate}
          />
        ))}
      </div>
    </div>
  );
}
