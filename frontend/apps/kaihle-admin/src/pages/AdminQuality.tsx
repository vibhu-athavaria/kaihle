import { useState } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { ShieldAlert } from "lucide-react";
import {
  useEvalSettings,
  useQualityFailures,
  useQualitySummary,
  type QualityBucket,
} from "../hooks/useAdminQuality";
import { BudgetPanel } from "../components/quality/BudgetPanel";
import { EvalSettingsPanel } from "../components/quality/EvalSettingsPanel";
import { QualityRatesTable } from "../components/quality/QualityRatesTable";
import { QualityFailuresTable } from "../components/quality/QualityFailuresTable";
import { LlmLogDetailModal } from "../components/llm-logs/LlmLogDetailModal";

const FAILURES_PAGE_SIZE = 20;
const SELECT =
  "font-['Inter'] text-sm border border-gray-200 rounded-lg px-3 py-1.5 min-h-[44px] text-gray-700 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2";
const FILTER_LABEL =
  "font-['Inter'] text-xs uppercase tracking-wide text-gray-400";

export function AdminQuality() {
  const { logout } = useAuth();
  const [task, setTask] = useState("");
  const [bucket, setBucket] = useState<QualityBucket>("none");
  const [failuresPage, setFailuresPage] = useState(1);
  const [openLogId, setOpenLogId] = useState<string | null>(null);

  const { data: settings } = useEvalSettings();
  const summary = useQualitySummary({ task: task || undefined, bucket });
  const failures = useQualityFailures({
    task: task || undefined,
    page: failuresPage,
    pageSize: FAILURES_PAGE_SIZE,
  });

  const failuresTotalPages = Math.max(
    1,
    Math.ceil((failures.data?.total ?? 0) / FAILURES_PAGE_SIZE),
  );

  return (
    <AdminLayout
      pageTitle="Quality"
      pageSubtitle="Pass rates on sampled production output"
      onLogout={logout}
    >
      <div className="space-y-6">
        <div
          role="note"
          className="flex items-start gap-3 rounded-2xl border border-brand-amber bg-brand-amber-light p-4"
        >
          <ShieldAlert
            className="w-5 h-5 shrink-0 text-brand-amber mt-0.5"
            aria-hidden="true"
          />
          <p className="font-['Inter'] text-sm text-gray-700">
            <strong>Best-effort scrubbing.</strong> Emails, phone numbers, URLs,
            ID-like numbers and known names are removed before text reaches the
            judge. Locations, relatives&apos; names and personal circumstances
            can be missed. Results hold only ids and pass/fail, never text.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BudgetPanel settings={settings} />
          <EvalSettingsPanel settings={settings} />
        </div>

        <section aria-label="Pass rates" className="space-y-3">
          <div className="flex items-center gap-4 flex-wrap">
            <h2 className="font-['Inter'] text-base font-bold text-brand-ink">
              Pass rates
            </h2>
            <div className="flex items-center gap-2">
              <label htmlFor="quality-task-filter" className={FILTER_LABEL}>
                Task
              </label>
              <select
                id="quality-task-filter"
                value={task}
                onChange={(e) => {
                  setTask(e.target.value);
                  setFailuresPage(1);
                }}
                className={SELECT}
              >
                <option value="">All tasks</option>
                {(settings?.available_tasks ?? []).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="quality-bucket" className={FILTER_LABEL}>
                Group
              </label>
              <select
                id="quality-bucket"
                value={bucket}
                onChange={(e) => setBucket(e.target.value as QualityBucket)}
                className={SELECT}
              >
                <option value="none">Whole window</option>
                <option value="week">By week</option>
              </select>
            </div>
          </div>
          <p className="font-['Inter'] text-xs text-gray-500">
            Rates show 95% Wilson intervals and the sample size n. Indeterminate
            results (for example an unparseable judge verdict) are counted
            separately and are not part of n. Production output has no answer
            key, so these are reference-free checks, not accuracy.
          </p>
          <QualityRatesTable
            rates={summary.data?.rates ?? []}
            loading={summary.isLoading}
            showWeek={bucket === "week"}
            truncated={summary.data?.truncated ?? false}
          />
        </section>

        <section aria-label="Failing checks" className="space-y-3">
          <h2 className="font-['Inter'] text-base font-bold text-brand-ink">
            Failing checks
          </h2>
          <QualityFailuresTable
            failures={failures.data?.failures ?? []}
            loading={failures.isLoading}
            page={failuresPage}
            totalPages={failuresTotalPages}
            onPageChange={setFailuresPage}
            onOpenLog={setOpenLogId}
          />
        </section>
      </div>

      <LlmLogDetailModal logId={openLogId} onClose={() => setOpenLogId(null)} />
    </AdminLayout>
  );
}
