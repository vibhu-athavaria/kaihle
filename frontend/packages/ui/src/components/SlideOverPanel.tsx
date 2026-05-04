import React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

interface SlideOverPanelProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
  titleClassName?: string;
}

export function SlideOverPanel({
  open,
  title,
  onClose,
  children,
  footer,
  width = "w-[400px]",
  titleClassName,
}: SlideOverPanelProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/20" />
        <Dialog.Content
          className={[
            "fixed top-0 right-0 bottom-0 z-50",
            width,
            "bg-white border-l border-brand-border flex flex-col",
            "focus:outline-none",
          ].join(" ")}
          style={{ boxShadow: "-8px 0 32px rgba(0,0,0,0.08)" }}
          aria-labelledby="slide-over-title"
        >
          {/* Header */}
          <div className="h-[50px] border-b border-brand-border flex items-center justify-between px-6 flex-shrink-0">
            <Dialog.Title
              id="slide-over-title"
              className={
                titleClassName ??
                "font-display font-bold text-[17px] text-brand-ink"
              }
            >
              {title}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-brand-muted hover:bg-gray-200 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 transition-colors"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </Dialog.Close>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-6 py-6">{children}</div>

          {/* Footer */}
          {footer && (
            <div className="border-t border-brand-border px-6 py-4 flex-shrink-0">
              {footer}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
