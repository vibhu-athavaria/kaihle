import { useNavigate } from "react-router-dom";
import { Lock } from "lucide-react";

export type DiagnosticStatus = "PENDING" | "IN_PROGRESS" | "COMPLETED";

export interface ClassCardProps {
  /** Unique identifier for the class */
  classId: string;
  /** Optional display name for the class (shown as card heading) */
  className?: string;
  /** Name of the subject for this class */
  subjectName: string;
  /** Name of the teacher for this class */
  teacherName: string;
  /** Current diagnostic status */
  diagnosticStatus: DiagnosticStatus;
  /** Optional diagnostic attempt ID for routing to in-progress assessment */
  diagnosticAttemptId?: string;
  /** Student count for the class */
  studentCount?: number;
}

export function ClassCard({
  classId,
  className,
  subjectName,
  teacherName,
  diagnosticStatus,
  diagnosticAttemptId,
  studentCount,
}: ClassCardProps) {
  const navigate = useNavigate();

  const isLocked =
    diagnosticStatus === "PENDING" || diagnosticStatus === "IN_PROGRESS";
  const isCompleted = diagnosticStatus === "COMPLETED";

  const handleClick = () => {
    if (isLocked) {
      // Navigate to diagnostic to unlock class, using attempt ID if available
      const diagnosticRoute = diagnosticAttemptId
        ? `/student/assessments/${diagnosticAttemptId}/take`
        : `/student/classes/${classId}/diagnostic`;
      navigate(diagnosticRoute);
    } else {
      // Navigate to topics (class content)
      navigate(`/student/classes/${classId}/topics`);
    }
  };

  // Determine dot color class based on status
  const getDotColorClass = () => {
    if (isLocked) return "bg-brand-gold"; // amber for locked
    if (isCompleted) return "bg-brand-primary"; // green for completed
    return "bg-brand-primary"; // default
  };

  // Determine which name to display as card heading
  const displayName = className || subjectName;

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`w-full text-left bg-white rounded-card border border-role-student-border p-3 shadow-card transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 min-h-[44px] ${
        isLocked ? "opacity-60" : ""
      }`}
    >
      {/* Header with dot and class/subject name */}
      <div className="flex items-center gap-1.5 mb-1">
        <span
          className={`w-[7px] h-[7px] rounded-full flex-shrink-0 ${getDotColorClass()}`}
          aria-label={`Status indicator: ${isLocked ? "locked" : "unlocked"}`}
        />
        <span className="font-sans font-semibold text-card-title text-brand-ink truncate">
          {displayName}
        </span>
      </div>

      {/* Meta info */}
      <div className="font-sans text-card-meta text-brand-body mb-1">
        {teacherName}
        {studentCount !== undefined && ` · ${studentCount} students`}
      </div>

      {/* CTA Footer */}
      <div
        className={`font-sans font-semibold text-card-action ${
          isLocked ? "text-brand-gold" : "text-brand-primary"
        }`}
      >
        {isLocked ? (
          <span className="flex items-center gap-1">
            <Lock className="w-3 h-3" aria-hidden="true" />
            Start diagnostic →
          </span>
        ) : (
          <span>View class →</span>
        )}
      </div>
    </button>
  );
}

export function ClassCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-brand-border p-3 animate-pulse">
      <div className="flex items-center gap-1.5 mb-1">
        <div className="w-[7px] h-[7px] rounded-full bg-brand-border" />
        <div className="h-3 w-24 bg-brand-border rounded" />
      </div>
      <div className="h-2 w-20 bg-brand-border-soft rounded mb-2" />
      <div className="h-2 w-16 bg-brand-border-soft rounded" />
    </div>
  );
}
