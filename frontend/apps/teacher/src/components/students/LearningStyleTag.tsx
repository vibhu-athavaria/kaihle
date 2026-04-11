const modalityConfig: Record<string, { icon: string; label: string }> = {
  visual: { icon: "👁", label: "Visual" },
  auditory: { icon: "👂", label: "Auditory" },
  reading_writing: { icon: "📖", label: "Reader" },
  kinesthetic: { icon: "🤲", label: "Hands-on" },
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
