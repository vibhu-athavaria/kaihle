import { useNavigate } from "react-router-dom";
import { Lock } from "lucide-react";

export type DiagnosticStatus = "PENDING" | "IN_PROGRESS" | "COMPLETED";

export interface ClassCardProps {
  classId: string;
  subjectName: string;
  teacherName: string;
  diagnosticStatus: DiagnosticStatus;
  /** Student count for the class */
  studentCount?: number;
}

export function ClassCard({
  classId,
  subjectName,
  teacherName,
  diagnosticStatus,
  studentCount,
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

  // Determine dot color class based on status
  const getDotColorClass = () => {
    if (isLocked) return "bg-brand-gold"; // amber for locked
    if (isCompleted) return "bg-brand-primary"; // green for completed
    return "bg-brand-primary"; // default
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`w-full text-left bg-white rounded-[10px] border border-brand-border p-3 transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 min-h-[44px] ${
        isLocked ? "opacity-60" : ""
      }`}
    >
      {/* Header with dot and class name */}
      <div className="flex items-center gap-1.5 mb-1">
        {" "}
        Hi there
        <span
          className={`w-[7px] h-[7px] rounded-full flex-shrink-0 ${getDotColorClass()}`}
          aria-label={`Status indicator: ${isLocked ? "locked" : "unlocked"}`}
        />
        <span className="text-[11px] font-semibold text-brand-ink truncate">
          {subjectName}
        </span>
      </div>

      {/* Meta info */}
      <div className="text-[9px] text-brand-muted mb-2">
        {teacherName}
        {studentCount !== undefined && ` · ${studentCount} students`}
      </div>

      {/* CTA Footer */}
      <div
        className={`text-[10px] font-semibold ${
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
