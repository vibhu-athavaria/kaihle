/**
 * Jest mock for @kaihle/ui.
 * Provides stub components for unit testing.
 */
import React from "react";

export const Button = ({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  children?: React.ReactNode;
  variant?: string;
  size?: string;
}) => React.createElement("button", props, children);

export const DashboardLayout = ({
  children,
}: {
  children: React.ReactNode;
  variant?: string;
  pageTitle?: string;
  onLogout?: () => void;
  topNavAction?: React.ReactNode;
}) =>
  React.createElement("div", { "data-testid": "dashboard-layout" }, children);

export const ErrorBoundary = ({
  children,
}: {
  children: React.ReactNode;
  role?: string;
}) => React.createElement("div", null, children);

export const EmptyState = ({
  title,
  description,
}: {
  title: string;
  description: string;
  emoji?: string;
  cta?: React.ReactNode;
}) => React.createElement("div", { role: "status" }, title, description);

export const Skeleton = () =>
  React.createElement("div", { className: "animate-pulse" });

export const ScoreRing = ({
  score,
  className,
}: {
  score: number | null;
  className?: string;
}) =>
  React.createElement("svg", {
    role: "img",
    "aria-label":
      score !== null ? `${Math.round(score * 100)}%` : "Not assessed",
    className,
  });
