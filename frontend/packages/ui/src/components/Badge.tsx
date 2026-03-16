import React from "react";

type BadgeVariant =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "gold";

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  pulse?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-brand-green-light text-brand-green",
  warning: "bg-brand-amber-light text-brand-amber",
  danger: "bg-brand-red-light text-brand-red",
  info: "bg-brand-light text-brand-primary border border-brand-mid",
  neutral: "bg-gray-100 text-brand-body",
  gold: "bg-brand-gold-light text-brand-gold-dark border border-brand-gold-mid",
};

export function Badge({
  variant = "neutral",
  children,
  pulse = false,
}: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 px-3 py-1 rounded-full",
        "text-xs font-bold",
        variantClasses[variant],
      ].join(" ")}
    >
      {pulse && (
        <span
          className="w-1.5 h-1.5 rounded-full bg-current animate-pulse"
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
