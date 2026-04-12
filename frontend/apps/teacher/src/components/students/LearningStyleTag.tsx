import { Eye, Headphones, Book, Hand } from "lucide-react";
import React from "react";

const modalityConfig: Record<string, { icon: React.ReactNode; label: string }> = {
  visual: { icon: <Eye className="w-3.5 h-3.5" />, label: "Visual" },
  auditory: { icon: <Headphones className="w-3.5 h-3.5" />, label: "Auditory" },
  reading_writing: { icon: <Book className="w-3.5 h-3.5" />, label: "Reader" },
  kinesthetic: { icon: <Hand className="w-3.5 h-3.5" />, label: "Hands-on" },
};

interface LearningStyleTagProps {
  modality: string | null;
}

export function LearningStyleTag({ modality }: LearningStyleTagProps) {
  if (!modality) {
    return <span className="text-brand-muted text-sm">—</span>;
  }

  const config = modalityConfig[modality];
  if (!config) {
    return <span className="text-brand-muted text-sm">—</span>;
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-gray-100 text-gray-700"
      aria-label={`Learning style: ${config.label}`}
    >
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  );
}
