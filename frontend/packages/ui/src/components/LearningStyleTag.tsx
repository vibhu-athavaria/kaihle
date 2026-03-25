/**
 * LearningStyleTag - Compact pill badge showing a student's dominant learning modality.
 * Used in Teacher app (student roster, profile) and Student app (settings).
 */
import React from "react";

type Modality =
  | "visual"
  | "auditory"
  | "reading_writing"
  | "kinesthetic"
  | null;
type TagVariant = "neutral" | "teacher" | "student";
type TagSize = "sm" | "md";

interface LearningStyleTagProps {
  /** Learning modality */
  modality: Modality;
  /** Size variant, default 'sm' */
  size?: TagSize;
  /** Colour scheme variant, default 'neutral' */
  variant?: TagVariant;
}

const modalityMap: Record<
  NonNullable<Modality>,
  { emoji: string; label: string }
> = {
  visual: { emoji: "👁", label: "Visual" },
  auditory: { emoji: "👂", label: "Auditory" },
  reading_writing: { emoji: "📖", label: "Reading & Writing" },
  kinesthetic: { emoji: "🤲", label: "Hands-on" },
};

const variantClasses: Record<TagVariant, string> = {
  neutral: "bg-gray-100 text-gray-700",
  teacher: "bg-amber-50 text-amber-700",
  student: "bg-green-50 text-brand-primary",
};

const sizeClasses: Record<TagSize, string> = {
  sm: "text-xs px-2.5 py-1 rounded-full",
  md: "text-sm px-3 py-1.5 rounded-full",
};

export function LearningStyleTag({
  modality,
  size = "sm",
  variant = "neutral",
}: LearningStyleTagProps): React.JSX.Element {
  if (modality === null) {
    return <span className="text-gray-400 text-xs">—</span>;
  }

  const { emoji, label } = modalityMap[modality];

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium ${sizeClasses[size]} ${variantClasses[variant]}`}
    >
      <span aria-hidden="true">{emoji}</span>
      {label}
    </span>
  );
}
