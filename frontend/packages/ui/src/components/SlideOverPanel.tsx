import React from "react";
import { X } from "lucide-react";

interface SlideOverPanelProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
}

export function SlideOverPanel({
  open,
  title,
  onClose,
  children,
  footer,
  width = "w-[400px]",
}: SlideOverPanelProps) {
  if (!open) return null;

  return (
    <div
      className={`absolute top-0 right-0 bottom-0 ${width} bg-white border-l border-brand-border flex flex-col z-20`}
      style={{ boxShadow: "-8px 0 32px rgba(0,0,0,0.08)" }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="slide-over-title"
    >
      {/* Header */}
      <div className="h-[50px] border-b border-brand-border flex items-center justify-between px-6 flex-shrink-0">
        <h2
          id="slide-over-title"
          className="font-display font-bold text-[17px] text-brand-ink"
        >
          {title}
        </h2>
        <button
          onClick={onClose}
          aria-label="Close"
          className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-brand-muted hover:bg-gray-200 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 transition-colors"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-6">{children}</div>

      {/* Footer */}
      {footer && (
        <div className="border-t border-gray-100 px-6 py-4 flex-shrink-0">
          {footer}
        </div>
      )}
    </div>
  );
}
