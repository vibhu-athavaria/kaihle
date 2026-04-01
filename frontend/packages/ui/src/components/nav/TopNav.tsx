import React from "react";
import { LogOut } from "lucide-react";

interface TopNavProps {
  pageTitle: string;
  pageSubtitle?: string;
  topNavAction?: React.ReactNode;
  variant?: "default" | "student" | "parent";
  onLogout?: () => void;
}

export function TopNav({
  pageTitle,
  pageSubtitle,
  topNavAction,
  variant = "default",
  onLogout,
}: TopNavProps) {
  if (variant === "parent") {
    return (
      <header className="h-14 bg-white border-b border-role-parent-border flex items-center px-4">
        <span className="font-['Lora'] italic font-semibold text-xl text-role-parent-ink">
          Kaihle
        </span>
        <div className="ml-auto flex items-center gap-3">
          {onLogout && (
            <button
              onClick={onLogout}
              className="p-2 hover:bg-gray-100 rounded-full"
              aria-label="Log out"
            >
              <LogOut className="w-5 h-5 text-role-parent-ink" />
            </button>
          )}
          {/* Settings accessible via avatar click - links to /parent/settings */}
          <a
            href="/parent/settings"
            className="w-8 h-8 rounded-full bg-amber-50 text-amber-700 text-sm font-semibold
                       flex items-center justify-center hover:opacity-80 transition-opacity
                       focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            aria-label="Account settings"
          >
            <span>P</span>
          </a>
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
          {onLogout && (
            <button
              onClick={onLogout}
              className="p-2 hover:bg-gray-100 rounded-full"
              aria-label="Log out"
            >
              <LogOut className="w-5 h-5 text-brand-ink" />
            </button>
          )}
          {/* Settings accessible via avatar click - links to /student/settings */}
          <a
            href="/student/settings"
            className="w-8 h-8 rounded-full bg-brand-primary flex items-center justify-center hover:opacity-80 transition-opacity focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            aria-label="Settings"
          >
            <span className="text-white text-xs font-medium">S</span>
          </a>
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
