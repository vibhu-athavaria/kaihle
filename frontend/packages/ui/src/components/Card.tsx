import React from "react";

type CardVariant = "default" | "interactive" | "highlighted" | "ghost";

interface CardProps {
  variant?: CardVariant;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

const variantClasses: Record<CardVariant, string> = {
  default: "bg-white border border-brand-border shadow-card",
  interactive:
    "bg-white border border-brand-border shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all cursor-pointer",
  highlighted: "bg-brand-light border border-brand-mid",
  ghost: "bg-transparent border border-brand-border",
};

export function Card({
  variant = "default",
  children,
  className = "",
  onClick,
}: CardProps) {
  return (
    <div
      className={["rounded-2xl p-5", variantClasses[variant], className].join(
        " ",
      )}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => (e.key === "Enter" || e.key === " ") && onClick()
          : undefined
      }
    >
      {children}
    </div>
  );
}
