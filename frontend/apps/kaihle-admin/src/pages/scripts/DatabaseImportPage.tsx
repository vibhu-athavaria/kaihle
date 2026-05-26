import { useState, useRef } from "react";
import { Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useImportDatabase } from "../../hooks/useDbTools";
import {
  ArrowLeft,
  Upload,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  Users,
} from "lucide-react";

export function DatabaseImportPage() {
  const { logout } = useAuth();
  const importDb = useImportDatabase();

  const [file, setFile] = useState<File | null>(null);
  const [overridePassword, setOverridePassword] = useState("test1234!");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isImporting = importDb.isPending;
  const result = importDb.data;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      // Reset any previous result when a new file is chosen
      importDb.reset();
    }
  };

  const handleImport = () => {
    if (!file) return;
    importDb.mutate({ file, overridePassword });
  };

  const fileSizeMB = file ? (file.size / 1024 / 1024).toFixed(1) : null;

  return (
    <AdminLayout pageTitle="Import Database" onLogout={logout}>
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
            <Upload className="w-4 h-4 text-brand-primary" aria-hidden="true" />
            Import Database
          </h1>
          <p className="text-xs text-role-admin-muted mt-1">
            Upload a .sql dump exported from production and restore it into the{" "}
            <strong>dev</strong> database. All user passwords will be replaced
            with the override password you set below.
          </p>
        </div>

        {/* Warning banner */}
        <div className="flex gap-3 p-4 bg-red-50 border border-red-200 rounded-xl mb-6">
          <AlertTriangle
            className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div>
            <p className="text-xs font-semibold text-red-800">
              Destructive operation — dev only
            </p>
            <p className="text-xs text-red-700 mt-0.5">
              This will overwrite all data in the current database. Only run
              this against your local dev environment. The import replaces
              existing tables using DROP / CREATE statements from the dump.
            </p>
          </div>
        </div>

        {/* Form card */}
        <div className="bg-white rounded-xl border border-role-admin-border p-6 space-y-6">
          {/* File picker */}
          <div>
            <label className="block text-xs font-medium text-role-admin-muted mb-2">
              SQL Dump File <span className="text-red-500">*</span>
            </label>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full flex flex-col items-center justify-center gap-2 px-4 py-8 border-2 border-dashed border-role-admin-border rounded-xl hover:border-brand-primary/50 hover:bg-brand-primary/5 transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              {file ? (
                <>
                  <FileText
                    className="w-6 h-6 text-brand-primary"
                    aria-hidden="true"
                  />
                  <span className="text-sm font-medium text-role-admin-ink">
                    {file.name}
                  </span>
                  <span className="text-xs text-role-admin-muted">
                    {fileSizeMB} MB — click to change
                  </span>
                </>
              ) : (
                <>
                  <Upload
                    className="w-6 h-6 text-role-admin-muted"
                    aria-hidden="true"
                  />
                  <span className="text-sm text-role-admin-subtle">
                    Click to select a .sql file
                  </span>
                  <span className="text-xs text-role-admin-muted">
                    Exported from Kaihle Admin → Export Database
                  </span>
                </>
              )}
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".sql"
              onChange={handleFileChange}
              className="sr-only"
              aria-label="Upload SQL dump file"
            />
          </div>

          {/* Password field */}
          <div>
            <label
              htmlFor="override-password"
              className="block text-xs font-medium text-role-admin-muted mb-1"
            >
              Override password for all users{" "}
              <span className="text-red-500">*</span>
            </label>
            <input
              id="override-password"
              type="text"
              value={overridePassword}
              onChange={(e) => setOverridePassword(e.target.value)}
              className="w-full border border-role-admin-border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-brand-primary"
              placeholder="test1234!"
              aria-describedby="override-password-hint"
            />
            <p
              id="override-password-hint"
              className="text-xs text-role-admin-muted mt-1 flex items-center gap-1"
            >
              <Users className="w-3 h-3" aria-hidden="true" />
              Every user in the imported DB will be able to log in with this
              password.
            </p>
          </div>

          {/* Submit */}
          <button
            type="button"
            onClick={handleImport}
            disabled={!file || !overridePassword || isImporting}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-primary text-white text-sm font-medium rounded-full hover:bg-brand-primary/90 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            {isImporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                Importing… this may take a minute
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" aria-hidden="true" />
                Import Database
              </>
            )}
          </button>
        </div>

        {/* Result output */}
        {result && (
          <div className="mt-6 bg-white rounded-xl border border-role-admin-border p-4">
            <div className="flex items-center gap-2 mb-3">
              {result.status === "completed" ? (
                <CheckCircle
                  className="w-5 h-5 text-green-500"
                  aria-hidden="true"
                />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" aria-hidden="true" />
              )}
              <span
                className={`text-sm font-semibold ${
                  result.status === "completed"
                    ? "text-green-700"
                    : "text-red-700"
                }`}
              >
                {result.status === "completed"
                  ? "Import complete"
                  : "Import failed"}
              </span>
              {result.status === "completed" && result.users_updated > 0 && (
                <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-brand-primary/10 text-brand-primary">
                  <Users className="w-3 h-3" aria-hidden="true" />
                  {result.users_updated} passwords reset
                </span>
              )}
            </div>

            {result.output && (
              <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-64">
                <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
                  {result.output}
                </pre>
              </div>
            )}

            {result.error && (
              <div className="bg-red-50 rounded-lg p-4 mt-3">
                <pre className="text-xs text-red-600 font-mono whitespace-pre-wrap">
                  {result.error}
                </pre>
              </div>
            )}

            {result.status === "completed" && (
              <p className="text-xs text-role-admin-muted mt-3">
                If Alembic migrations are ahead of the dump, run{" "}
                <code className="font-mono bg-gray-100 px-1 rounded">
                  docker compose exec backend alembic upgrade head
                </code>{" "}
                after importing.
              </p>
            )}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
