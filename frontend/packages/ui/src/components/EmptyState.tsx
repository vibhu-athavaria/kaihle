import React from "react";

interface EmptyStateProps {
  emoji: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({
  emoji,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="text-center py-16 px-6">
      <div className="text-4xl mb-4" role="img" aria-label={title}>
        {emoji}
      </div>
      <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
        {title}
      </h3>
      <p className="text-brand-body text-sm max-w-sm mx-auto leading-relaxed">
        {description}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
