import { Link } from "react-router-dom";
import { useScriptsList, ScriptDefinition } from "../../hooks/useScripts";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  Terminal,
  Database,
  BookOpen,
  FileText,
  XCircle,
  FlaskConical,
} from "lucide-react";

const AI_SMOKE_TESTS = [
  {
    name: "concept-explanation",
    title: "Concept Explanation",
    description:
      "Generate a personalised subtopic explanation with optional MCQ check question.",
  },
  {
    name: "mini-course",
    title: "Mini-Course Generation",
    description:
      "Generate interest-personalised explanations across 4 interest categories for a topic.",
  },
  {
    name: "lesson-plan",
    title: "Lesson Plan",
    description:
      "Generate a lesson plan preview for a class. Full LLM + validation pipeline, no DB write.",
  },
  {
    name: "practice-quiz",
    title: "Practice Quiz",
    description:
      "Generate a practice quiz at a given mastery level, with explanation context diagnostics.",
  },
];

function getCategoryIcon(category: string) {
  switch (category) {
    case "database":
      return Database;
    case "curriculum":
      return BookOpen;
    case "review":
      return FileText;
    default:
      return Terminal;
  }
}

function ScriptCard({ script }: { script: ScriptDefinition }) {
  const Icon = getCategoryIcon(script.category);

  return (
    <Link
      to={`/kaihle-admin/scripts/${script.name}`}
      className="block p-4 rounded-xl border border-role-admin-border hover:border-brand-primary/50 bg-white hover:bg-brand-primary/5 transition-all"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
          <Icon className="w-5 h-5 text-brand-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-role-admin-ink truncate">
            {script.name}
          </h3>
          <p className="text-xs text-role-admin-subtle mt-1 line-clamp-2">
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
      </div>
    </Link>
  );
}

export function ScriptsPage() {
  const { logout } = useAuth();
  const { data, isLoading, isError } = useScriptsList();

  // Group scripts by category
  const scriptsByCategory =
    data?.scripts.reduce(
      (acc, script) => {
        const category = script.category || "general";
        if (!acc[category]) {
          acc[category] = [];
        }
        acc[category].push(script);
        return acc;
      },
      {} as Record<string, ScriptDefinition[]>,
    ) || {};

  const categoryLabels: Record<string, string> = {
    database: "Database Scripts",
    curriculum: "Curriculum Scripts",
    review: "Review Scripts",
    general: "General Scripts",
  };

  return (
    <AdminLayout pageTitle="Scripts" onLogout={logout}>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-sm font-bold text-role-admin-ink flex items-center gap-2">
            <Terminal className="w-4 h-4 text-brand-primary" />
            Scripts
          </h1>
          <p className="text-xs text-role-admin-muted mt-1">
            Execute backend scripts to manage curriculum, questions, and data.
          </p>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-12">
            <XCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
            <p className="text-sm text-red-600">Failed to load scripts</p>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(scriptsByCategory).map(([category, scripts]) => (
              <div key={category}>
                <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-3">
                  {categoryLabels[category] || category}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {scripts.map((script) => (
                    <ScriptCard key={script.name} script={script} />
                  ))}
                </div>
              </div>
            ))}

            <div>
              <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-3">
                AI Smoke Tests
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {AI_SMOKE_TESTS.map((test) => (
                  <Link
                    key={test.name}
                    to={`/kaihle-admin/scripts/smoke-tests/${test.name}`}
                    className="block p-4 rounded-xl border border-role-admin-border hover:border-brand-primary/50 bg-white hover:bg-brand-primary/5 transition-all"
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
                        <FlaskConical className="w-5 h-5 text-brand-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold text-role-admin-ink truncate">
                          {test.title}
                        </h3>
                        <p className="text-xs text-role-admin-subtle mt-1 line-clamp-2">
                          {test.description}
                        </p>
                        <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-[10px] font-medium bg-brand-primary/10 text-brand-primary">
                          AI / LLM
                        </span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
