import React from "react";

interface TopNavProps {
  pageTitle: string;
  pageSubtitle?: string;
  topNavAction?: React.ReactNode;
  variant?: "default" | "student" | "parent";
}

export function TopNav({
  pageTitle,
  pageSubtitle,
  topNavAction,
  variant = "default",
}: TopNavProps) {
  if (variant === "parent") {
    return (
      <header className="h-14 bg-white border-b border-role-parent-border flex items-center px-4">
        <span className="font-['Lora'] italic font-semibold text-xl text-role-parent-ink">
          Kaihle
        </span>
        <div className="ml-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-primary" />
        </div>
      </header>
    );
  }

  if (variant === "student") {
    return (
      <header className="h-14 bg-white border-b border-role-student-border flex items-center px-4">
        <span className="font-display font-bold text-lg text-brand-ink">
          Kaihle
        </span>
        <div className="ml-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-primary" />
        </div>
      </header>
    );
  }

  return (
    <header className="h-14 bg-white border-b border-brand-border flex items-center px-6">
      <div>
        <h1 className="font-display font-bold text-xl text-brand-ink">
          {pageTitle}
        </h1>
        {pageSubtitle && (
          <p className="text-sm text-brand-body">{pageSubtitle}</p>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">{topNavAction}</div>
    </header>
  );
}
