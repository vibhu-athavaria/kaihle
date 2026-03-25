import React from "react";

/**
 * Role type for role-aware error fallback UI.
 * Matches the five Kaihle user roles.
 */
export type Role =
  | "teacher"
  | "student"
  | "parent"
  | "school-admin"
  | "kaihle-admin"
  | "onboarding";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /**
   * Optional custom fallback component rendered when an error is caught.
   * If not provided, a role-aware default fallback is shown.
   */
  fallback?: React.ReactNode;
  /**
   * The Kaihle role determines which design system the fallback uses.
   * Falls back to a neutral style if not specified.
   */
  role?: Role;
  /**
   * Optional callback invoked whenever an error is caught.
   * Use this for error reporting services (Sentry, Datadog, etc.).
   */
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  /**
   * Optional callback invoked when the user clicks the reload button.
   * Defaults to window.location.reload() if not provided.
   * Useful for testability and custom reload behavior.
   */
  onReload?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * KaihleErrorFallback is the default error UI shown inside the ErrorBoundary.
 * It adapts its typography and colours to the current user role.
 *
 * Typography by role:
 * - kaihle-admin: Inter (font-['Inter'])
 * - All others: Fraunces for headings (font-display), Nunito for UI (font-sans)
 */
function KaihleErrorFallback({
  role = "teacher",
  error,
  onReload,
}: {
  role?: Role;
  error: Error | null;
  onReload?: () => void;
}) {
  const isKaihleAdmin = role === "kaihle-admin";

  const containerClass = isKaihleAdmin
    ? "flex flex-col items-center justify-center min-h-screen bg-[#f8f9fb] font-['Inter'] text-center p-6"
    : "flex flex-col items-center justify-center min-h-screen bg-[#f5f7f1] font-sans text-center p-6";

  const headingClass = isKaihleAdmin
    ? "text-2xl font-semibold text-brand-ink mb-4"
    : "text-2xl font-display font-bold text-brand-ink mb-4";

  const messageClass = "text-brand-muted text-sm max-w-md mb-6";

  const buttonClass = [
    "min-h-[44px] px-6 py-2 rounded-lg font-semibold text-white",
    "bg-brand-primary hover:bg-brand-primary/90",
    "focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
    "transition-colors",
  ].join(" ");

  return (
    <div className={containerClass} role="alert" aria-live="assertive">
      <div
        className="w-12 h-12 rounded-full bg-brand-red/10 flex items-center justify-center mb-4"
        aria-hidden="true"
      >
        <svg
          className="w-6 h-6 text-brand-red"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <h1 className={headingClass}>Something went wrong</h1>
      <p className={messageClass}>
        {error?.message ?? "An unexpected error occurred. Please try again."}
      </p>
      <button
        className={buttonClass}
        onClick={() => (onReload ?? window.location.reload)()}
        type="button"
      >
        Reload page
      </button>
    </div>
  );
}

/**
 * ErrorBoundary is a React class component that catches JavaScript errors
 * anywhere in its child component tree and displays a fallback UI
 * instead of crashing the whole application.
 *
 * WCAG 2.1 SC 4.1.2 — Name, Role, Value: the fallback has `role="alert"`
 * so screen readers announce the error immediately.
 *
 * WCAG 2.1 SC 3.3.1 — Error Identification: the error message is shown
 * in the fallback so users know what went wrong.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render shows the fallback UI.
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log to console for development visibility.
    // In production, replace or augment this with your error reporting service.
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <KaihleErrorFallback
          role={this.props.role}
          error={this.state.error}
          onReload={this.props.onReload}
        />
      );
    }

    return this.props.children;
  }
}
