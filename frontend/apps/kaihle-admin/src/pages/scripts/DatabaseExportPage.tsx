import { Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useExportDatabase } from "../../hooks/useDbTools";
import {
  ArrowLeft,
  Download,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from "lucide-react";

export function DatabaseExportPage() {
  const { logout } = useAuth();
  const exportDb = useExportDatabase();

  const isExporting = exportDb.isPending;
  const isSuccess = exportDb.isSuccess;
  const isError = exportDb.isError;

  return (
    <AdminLayout pageTitle="Export Database" onLogout={logout}>
      <div className="p-6 max-w-2xl">
        {/* Back link */}
        <Link
          to="/kaihle-admin/scripts"
          className="inline-flex items-center gap-1 text-xs text-role-admin-subtle hover:text-brand-primary mb-6"
        >
          <ArrowLeft className="w-3 h-3" aria-hidden="true" />
          Back to Scripts
        </Link>

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-sm font-bold text-role-admin-ink flex items-center gap-2">
            <Download
              className="w-4 h-4 text-brand-primary"
              aria-hidden="true"
            />
            Export Database
          </h1>
          <p className="text-xs text-role-admin-muted mt-1">
            Dump the current database as a plain-SQL file. Run this from the{" "}
            <strong>production</strong> Kaihle Admin to download a snapshot.
          </p>
        </div>

        {/* Warning banner */}
        <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl mb-6">
          <AlertTriangle
            className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div>
            <p className="text-xs font-semibold text-amber-800">
              Run this on production only
            </p>
            <p className="text-xs text-amber-700 mt-0.5">
              The export dumps whichever database{" "}
              <code className="font-mono bg-amber-100 px-1 rounded">
                DATABASE_URL
              </code>{" "}
              points to. Make sure you are logged into the{" "}
              <strong>production</strong> Kaihle Admin before clicking Export.
            </p>
          </div>
        </div>

        {/* Action card */}
        <div className="bg-white rounded-xl border border-role-admin-border p-6">
          <div className="mb-5">
            <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
              What this does
            </h2>
            <ul className="text-xs text-role-admin-subtle space-y-1 list-disc list-inside">
              <li>Runs pg_dump with --clean --if-exists (safe to re-import)</li>
              <li>Excludes Celery internal tables</li>
              <li>
                Strips ownership / ACL statements (no superuser needed on
                import)
              </li>
              <li>Downloads as kaihle_export_YYYY-MM-DD.sql</li>
            </ul>
          </div>

          <button
            type="button"
            onClick={() => exportDb.mutate()}
            disabled={isExporting}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-primary text-white text-sm font-medium rounded-full hover:bg-brand-primary/90 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                Exporting…
              </>
            ) : (
              <>
                <Download className="w-4 h-4" aria-hidden="true" />
                Export &amp; Download
              </>
            )}
          </button>

          {/* Result feedback */}
          {isSuccess && (
            <div className="flex items-center gap-2 mt-4 text-sm text-green-700">
              <CheckCircle
                className="w-4 h-4 text-green-500 flex-shrink-0"
                aria-hidden="true"
              />
              Download started — check your browser's downloads folder.
            </div>
          )}

          {isError && (
            <div className="flex items-start gap-2 mt-4">
              <XCircle
                className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5"
                aria-hidden="true"
              />
              <div>
                <p className="text-xs font-semibold text-red-700">
                  Export failed
                </p>
                <p className="text-xs text-red-600 mt-0.5">
                  {exportDb.error instanceof Error
                    ? exportDb.error.message
                    : "An unexpected error occurred. Check server logs."}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
