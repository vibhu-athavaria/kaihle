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

export const Modal = ({
  children,
  open,
  onOpenChange,
  title,
}: {
  children?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  title?: string;
}) =>
  open
    ? React.createElement(
        "div",
        { role: "dialog", "aria-label": title },
        children,
      )
    : null;

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

export const SkeletonCard = () =>
  React.createElement("div", { className: "animate-pulse" });

export const Badge = ({
  children,
  variant,
}: {
  children: React.ReactNode;
  variant?: string;
}) =>
  React.createElement(
    "span",
    { className: `badge badge-${variant}` },
    children,
  );

export const toast = {
  success: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
};
