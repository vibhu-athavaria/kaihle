import { Eye } from "lucide-react";

export interface ImpersonationBannerProps {
  /** Display name of the user being viewed as. */
  userName: string;
  /** Role of the user being viewed as, e.g. "STUDENT". */
  userRole: string;
  /** Display name of the Kaihle Admin who started this session. */
  impersonatorName: string;
  onExit: () => void;
}

/**
 * Persistent, non-dismissable bar shown for the whole life of a Kaihle Admin
 * impersonation session.
 *
 * Deliberately anchored to the bottom rather than the top: every role's layout
 * already owns the top of the viewport (sticky headers, top nav), and a fixed
 * top bar would overlap them differently in each of the five apps. The bottom
 * edge is uniformly free.
 *
 * Presentational only — it takes no dependency on the auth package, so
 * packages/ui stays auth-agnostic. See ImpersonationBar in @kaihle/auth for the
 * container that supplies these props.
 */
export function ImpersonationBanner({
  userName,
  userRole,
  impersonatorName,
  onExit,
}: ImpersonationBannerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-0 inset-x-0 z-50 bg-brand-amber-light border-t-2 border-brand-amber"
    >
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2.5">
        <Eye className="w-5 h-5 text-brand-amber shrink-0" aria-hidden="true" />
        <p className="flex-1 font-sans text-sm text-brand-ink">
          Viewing as{" "}
          <span className="font-bold">
            {userName} ({userRole.replace("_", " ").toLowerCase()})
          </span>
          . Signed in as {impersonatorName}. Anything you do here is recorded
          against your admin account.
        </p>
        <button
          type="button"
          onClick={onExit}
          className="shrink-0 rounded-full border border-brand-amber bg-white px-4 py-2 font-sans text-xs font-bold text-brand-ink transition-colors hover:bg-brand-amber-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 min-h-[44px]"
        >
          Exit
        </button>
      </div>
    </div>
  );
}
