import { useNavigate } from "react-router-dom";
import { Lock, MessageSquare, ClipboardCheck } from "lucide-react";

export type DiagnosticStatus = "PENDING" | "IN_PROGRESS" | "COMPLETED";

export interface ClassCardProps {
  classId: string;
  subjectName: string;
  gradeName: string;
  teacherName: string;
  diagnosticStatus: DiagnosticStatus;
  hasNewMessages: boolean;
  hasNewProgressCheck: boolean;
  topicCount?: number;
}

export function ClassCard({
  classId,
  subjectName,
  gradeName,
  teacherName,
  diagnosticStatus,
  hasNewMessages,
  hasNewProgressCheck,
  topicCount,
}: ClassCardProps) {
  const navigate = useNavigate();

  const isLocked =
    diagnosticStatus === "PENDING" || diagnosticStatus === "IN_PROGRESS";
  const isCompleted = diagnosticStatus === "COMPLETED";

  const handleClick = () => {
    if (isLocked) {
      // Navigate to diagnostic to unlock class
      navigate(`/student/classes/${classId}/diagnostic`);
    } else {
      // Navigate to topics (class content)
      navigate(`/student/classes/${classId}/topics`);
    }
  };

  // Determine border color based on status
  const getBorderClass = () => {
    if (isLocked) return "border-brand-border";
    if (isCompleted) return "border-brand-mid";
    return "border-brand-border";
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`w-full text-left bg-white rounded-2xl border-[1.5px] ${getBorderClass()} p-4 transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
        isLocked ? "opacity-60 cursor-pointer" : "cursor-pointer"
      }`}
    >
      {/* Header with subject icon and badges */}
      <div className="flex items-start justify-between mb-3">
        <div className="relative">
          {/* Subject icon placeholder - uses first letter as fallback */}
          <div className="w-10 h-10 rounded-full bg-brand-light flex items-center justify-center">
            <span className="text-lg font-bold text-brand-primary">
              {subjectName.charAt(0).toUpperCase()}
            </span>
          </div>
          {/* Lock overlay when diagnostic not complete */}
          {isLocked && (
            <div className="absolute -top-1 -right-1 w-5 h-5 bg-brand-muted rounded-full flex items-center justify-center">
              <Lock className="w-3 h-3 text-white" aria-hidden="true" />
            </div>
          )}
        </div>

        {/* Alert badges - only show when unlocked */}
        {isCompleted && (hasNewMessages || hasNewProgressCheck) && (
          <div className="flex items-center gap-1">
            {hasNewMessages && (
              <span
                className="w-5 h-5 rounded-full bg-brand-gold flex items-center justify-center"
                aria-label="New message"
                role="img"
              >
                <MessageSquare
                  className="w-3 h-3 text-white"
                  aria-hidden="true"
                />
              </span>
            )}
            {hasNewProgressCheck && (
              <span
                className="w-5 h-5 rounded-full bg-brand-primary flex items-center justify-center"
                aria-label="New progress check"
                role="img"
              >
                <ClipboardCheck
                  className="w-3 h-3 text-white"
                  aria-hidden="true"
                />
              </span>
            )}
          </div>
        )}
      </div>

      {/* Class info */}
      <div className="space-y-1">
        <h3 className="font-sans font-semibold text-base text-brand-ink line-clamp-1">
          {subjectName}
        </h3>
        <p className="font-sans text-xs text-brand-muted">
          {gradeName} · {teacherName}
        </p>
        {topicCount !== undefined && isCompleted && (
          <p className="font-sans text-xs text-brand-muted">
            {topicCount} {topicCount === 1 ? "topic" : "topics"}
          </p>
        )}
      </div>

      {/* Locked state banner */}
      {isLocked && (
        <div className="mt-3 pt-3 border-t border-brand-border-soft">
          <div className="flex items-center justify-between">
            <span className="font-sans text-xs font-medium text-brand-body">
              Complete diagnostic to unlock
            </span>
            <ChevronRightIcon />
          </div>
        </div>
      )}
    </button>
  );
}

function ChevronRightIcon() {
  return (
    <svg
      className="w-4 h-4 text-brand-muted"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5l7 7-7 7"
      />
    </svg>
  );
}

export function ClassCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border p-4 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-full bg-brand-border" />
        <div className="w-5 h-5 rounded-full bg-brand-border" />
      </div>
      <div className="space-y-2">
        <div className="h-4 w-24 bg-brand-border rounded" />
        <div className="h-3 w-32 bg-brand-border-soft rounded" />
      </div>
    </div>
  );
}
