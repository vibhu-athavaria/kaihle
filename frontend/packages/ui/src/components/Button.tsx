import React from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-brand-primary hover:bg-brand-dark text-white shadow-btn",
  secondary:
    "bg-white hover:bg-gray-50 text-brand-ink border border-brand-border",
  danger: "bg-brand-red hover:bg-red-600 text-white",
  ghost: "bg-white/15 hover:bg-white/25 text-white border border-white/30",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-4 py-2 text-xs min-h-[44px]",
  md: "px-5 py-2.5 text-sm min-h-[44px]",
  lg: "px-7 py-3.5 text-base min-h-[44px]",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center gap-2 font-sans font-bold",
        "rounded-full transition-colors",
        "focus-visible:outline-none focus-visible:ring-2",
        "focus-visible:ring-brand-primary focus-visible:ring-offset-2",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(" ")}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span
          className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"
          aria-hidden="true"
        />
      ) : icon ? (
        <span className="w-4 h-4" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children}
    </button>
  );
}
