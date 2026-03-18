import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";

export type PendingAction =
  | {
      type: "study-plan";
      classId: string;
      className: string;
      studentCount: number;
    }
  | {
      type: "assessment-review";
      classId: string;
      className: string;
      assessmentName: string;
      studentCount: number;
    }
  | { type: "no-assessments"; classId: string; className: string };

interface PendingActionBannerProps {
  action: PendingAction;
}

function getActionMessage(action: PendingAction): string {
  switch (action.type) {
    case "study-plan":
      return `${action.studentCount} student${
        action.studentCount !== 1 ? "s" : ""
      } need study plans in ${action.className}`;
    case "assessment-review":
      return `${action.studentCount} student${
        action.studentCount !== 1 ? "s" : ""
      } completed ${action.assessmentName} — view results`;
    case "no-assessments":
      return `No assessments yet for ${action.className} — create one to see gaps`;
  }
}

function getActionLink(action: PendingAction): string {
  switch (action.type) {
    case "study-plan":
      return `/teacher/classes/${action.classId}/gap-map`;
    case "assessment-review":
      return `/teacher/classes/${action.classId}/assessments`;
    case "no-assessments":
      return `/teacher/classes/${action.classId}/assessments`;
  }
}

export function PendingActionBanner({ action }: PendingActionBannerProps) {
  return (
    <div className="bg-brand-gold-light border border-brand-gold-mid rounded-xl p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <AlertTriangle className="w-5 h-5 text-brand-gold" />
        <span className="text-sm font-medium text-brand-ink">
          {getActionMessage(action)}
        </span>
      </div>
      <Link
        to={getActionLink(action)}
        className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark"
      >
        Go →
      </Link>
    </div>
  );
}
