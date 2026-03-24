import React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

type ModalMaxWidth = "sm" | "md" | "lg";

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  maxWidth?: ModalMaxWidth;
  hideCloseButton?: boolean;
  titleClassName?: string;
}

const maxWidthMap: Record<ModalMaxWidth, string> = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
};

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  maxWidth = "md",
  hideCloseButton = false,
  titleClassName,
}: ModalProps) {
  const defaultTitleClass =
    "font-fraunces text-xl text-brand-ink font-bold mb-1 pr-8";

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        {/* Backdrop overlay */}
        <Dialog.Overlay
          className={[
            "fixed inset-0 z-40",
            "bg-black/40 backdrop-blur-[2px]",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
            "motion-safe:transition-opacity motion-safe:duration-200",
          ].join(" ")}
        />

        {/* Modal panel */}
        <Dialog.Content
          className={[
            "fixed left-1/2 top-1/2 z-50",
            "-translate-x-1/2 -translate-y-1/2",
            "w-[calc(100vw-32px)]",
            maxWidthMap[maxWidth],
            "bg-white rounded-2xl shadow-xl p-6",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
            "motion-safe:transition-all motion-safe:duration-200",
            "focus:outline-none",
          ].join(" ")}
        >
          {/* Close button */}
          {!hideCloseButton && (
            <Dialog.Close
              className={[
                "absolute right-4 top-4",
                "w-8 h-8 rounded-full",
                "flex items-center justify-center",
                "text-gray-400 hover:text-gray-600 hover:bg-gray-100",
                "transition-colors",
                "focus-visible:outline-none focus-visible:ring-2",
                "focus-visible:ring-brand-primary focus-visible:ring-offset-1",
              ].join(" ")}
              aria-label="Close"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </Dialog.Close>
          )}

          {/* Title */}
          <Dialog.Title className={titleClassName ?? defaultTitleClass}>
            {title}
          </Dialog.Title>

          {/* Optional description */}
          {description && (
            <Dialog.Description className="text-sm text-gray-500 mb-4">
              {description}
            </Dialog.Description>
          )}

          {/* Body content */}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
