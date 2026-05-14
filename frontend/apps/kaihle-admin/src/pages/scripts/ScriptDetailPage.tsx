import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  useScriptsList,
  useExecuteScript,
  ScriptParameter,
} from "../../hooks/useScripts";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  ArrowLeft,
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
} from "lucide-react";

function ParameterInput({
  param,
  value,
  onChange,
}: {
  param: ScriptParameter;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (param.type === "boolean") {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
          className="w-4 h-4 rounded border-role-admin-border text-brand-primary focus:ring-brand-primary"
        />
        <span className="text-sm text-role-admin-ink">
          {param.description || param.name}
        </span>
      </label>
    );
  }

  if (param.type === "number") {
    return (
      <div>
        <label className="block text-xs font-medium text-role-admin-muted mb-1">
          {param.description || param.name}
          {param.required && <span className="text-red-500"> *</span>}
        </label>
        <input
          type="number"
          step="any"
          value={(value as number) ?? param.default ?? ""}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-full border border-role-admin-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
          placeholder={param.default?.toString() || ""}
        />
      </div>
    );
  }

  // String input - use password type for api_key
  const isPassword =
    param.name === "api_key" ||
    param.name.includes("secret") ||
    param.name.includes("key");

  return (
    <div>
      <label className="block text-xs font-medium text-role-admin-muted mb-1">
        {param.description || param.name}
        {param.required && <span className="text-red-500"> *</span>}
      </label>
      <input
        type={isPassword ? "password" : "text"}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-role-admin-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
        placeholder={param.default?.toString() || ""}
      />
    </div>
  );
}

export function ScriptDetailPage() {
  const { scriptName } = useParams<{ scriptName: string }>();
  const { logout } = useAuth();
  const { data: scripts, isLoading } = useScriptsList();
  const executeScript = useExecuteScript();

  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [envVars, setEnvVars] = useState<Record<string, string>>({});
  const [apiKeyInput, setApiKeyInput] = useState("");

  const script = scripts?.scripts.find((s) => s.name === scriptName);

  useEffect(() => {
    if (script) {
      // Initialize parameters with defaults
      const defaults: Record<string, unknown> = {};
      const envDefaults: Record<string, string> = {};

      script.parameters.forEach((param) => {
        if (param.default !== null && param.default !== undefined) {
          const defaultVal = param.default as unknown;
          if (param.type === "boolean") {
            defaults[param.name] = Boolean(defaultVal);
          } else if (param.type === "number") {
            defaults[param.name] = Number(defaultVal) || 0;
          } else {
            defaults[param.name] = String(defaultVal);
          }
        }
      });

      setParameters(defaults);
      setEnvVars(envDefaults);
    }
  }, [script]);

  const handleParameterChange = (name: string, value: unknown) => {
    setParameters((prev) => ({ ...prev, [name]: value }));
  };

  const handleExecute = async () => {
    if (!scriptName) return;

    // If API key is provided in the top box, add it to env vars (for non-seed_subtopic_content scripts)
    const finalEnvVars = { ...envVars };
    if (apiKeyInput && scriptName !== "seed_subtopic_content") {
      finalEnvVars["OPENROUTER_API_KEY"] = apiKeyInput;
    }

    try {
      await executeScript.mutateAsync({
        scriptName,
        parameters,
        envVars: finalEnvVars,
      });
    } catch (error) {
      // Error is handled in the mutation result
    }
  };

  if (isLoading) {
    return (
      <AdminLayout pageTitle="Loading..." onLogout={logout}>
        <div className="p-6">
          <div className="animate-pulse h-96 bg-gray-200 rounded-xl" />
        </div>
      </AdminLayout>
    );
  }

  if (!script) {
    return (
      <AdminLayout pageTitle="Script Not Found" onLogout={logout}>
        <div className="p-6">
          <Link
            to="/kaihle-admin/scripts"
            className="inline-flex items-center gap-1 text-xs text-role-admin-subtle hover:text-brand-primary mb-4"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to Scripts
          </Link>
          <div className="text-center py-12">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
            <p className="text-sm text-red-600">Script not found</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  const isExecuting = executeScript.isPending;
  const result = executeScript.data;

  // Check if script has api_key as a parameter
  const hasApiKeyParam = script.parameters.some((p) => p.name === "api_key");

  // Show top API key box only if required AND doesn't have api_key in parameters
  const showApiKeyBox = script.requires_api_key && !hasApiKeyParam;

  return (
    <AdminLayout pageTitle={script.name} onLogout={logout}>
      <div className="p-6">
        <Link
          to="/kaihle-admin/scripts"
          className="inline-flex items-center gap-1 text-xs text-role-admin-subtle hover:text-brand-primary mb-4"
        >
          <ArrowLeft className="w-3 h-3" />
          Back to Scripts
        </Link>

        {/* Script Info */}
        <div className="bg-white rounded-xl border border-role-admin-border p-4 mb-6">
          <h1 className="text-sm font-bold text-role-admin-ink">
            {script.name}
          </h1>
          <p className="text-xs text-role-admin-subtle mt-1">
            {script.description}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-role-admin-subtle">
              {script.category}
            </span>
            {script.requires_api_key && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-700">
                Requires API Key
              </span>
            )}
          </div>
        </div>

        {/* Parameters Form */}
        <div className="bg-white rounded-xl border border-role-admin-border p-4 mb-6">
          <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4">
            Parameters
          </h2>

          {showApiKeyBox && (
            <div className="mb-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
              <label className="block text-xs font-medium text-amber-800 mb-1">
                OpenRouter API Key
              </label>
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                className="w-full border border-amber-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-amber-500"
                placeholder="sk-or-..."
              />
              <p className="text-xs text-amber-600 mt-1">
                Or set OPENROUTER_API_KEY environment variable
              </p>
            </div>
          )}

          <div className="space-y-4">
            {script.parameters.map((param) => (
              <ParameterInput
                key={param.name}
                param={param}
                value={parameters[param.name]}
                onChange={(value) => handleParameterChange(param.name, value)}
              />
            ))}
          </div>

          <button
            type="button"
            onClick={handleExecute}
            disabled={isExecuting}
            className="mt-4 w-full inline-flex items-center justify-center gap-2 px-4 py-2 bg-brand-primary text-white text-sm font-medium rounded-full hover:bg-brand-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isExecuting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Executing...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Execute Script
              </>
            )}
          </button>
        </div>

        {/* Result Output */}
        {result && (
          <div className="bg-white rounded-xl border border-role-admin-border p-4">
            <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4">
              Result
            </h2>

            <div className="flex items-center gap-2 mb-3">
              {result.status === "completed" ? (
                <CheckCircle className="w-5 h-5 text-green-500" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" />
              )}
              <span
                className={`text-sm font-medium ${
                  result.status === "completed"
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {result.status === "completed" ? "Success" : "Failed"}
              </span>
              {result.return_code !== null && (
                <span className="text-xs text-role-admin-muted">
                  (Exit code: {result.return_code})
                </span>
              )}
            </div>

            {result.output !== null && result.output !== undefined && (
              <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-96">
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
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
