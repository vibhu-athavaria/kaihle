import { useState } from "react";
import { AdminLayout, Skeleton } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useAdminLlmUsage, LlmUsageGroupBy } from "../hooks/useAdminLlmUsage";
import { UsageKPIRow } from "../components/llm-usage/UsageKPIRow";
import { UsageBucketTable } from "../components/llm-usage/UsageBucketTable";
import { RecentRunsTable } from "../components/llm-usage/RecentRunsTable";

const RUNS_PAGE_SIZE = 10;

export function AdminLlmUsage() {
  const { logout } = useAuth();
  const [groupBy, setGroupBy] = useState<LlmUsageGroupBy>("component");
  const [runsPage, setRunsPage] = useState(1);

  const { data, isLoading } = useAdminLlmUsage({
    groupBy,
    page: 1,
    pageSize: 20,
  });
  const { data: runsData, isLoading: runsLoading } = useAdminLlmUsage({
    groupBy: "run_id",
    page: runsPage,
    pageSize: RUNS_PAGE_SIZE,
  });

  const buckets = data?.buckets ?? [];
  const summary = data?.summary;
  const runs = runsData?.buckets ?? [];

  return (
    <AdminLayout pageTitle="LLM usage" onLogout={logout}>
      <div className="space-y-6">
        <section>
          <h2 className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">
            Spend overview
          </h2>
          <UsageKPIRow summary={summary} loading={isLoading} />
        </section>

        <section>
          <h2 className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">
            Usage by {groupBy.replace("_", " ")}
          </h2>
          <UsageBucketTable
            buckets={buckets}
            loading={isLoading}
            groupBy={groupBy}
            onGroupByChange={setGroupBy}
          />
        </section>

        <section>
          <h2 className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">
            Recent runs
          </h2>
          <RecentRunsTable
            runs={runs}
            loading={runsLoading}
            page={runsPage}
            pageSize={RUNS_PAGE_SIZE}
            totalRuns={runsData?.total_buckets ?? 0}
            onPageChange={setRunsPage}
          />
        </section>

        <section>
          <h2 className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">
            Unit costs
          </h2>
          <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
            {isLoading &&
              [...Array(3)].map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-3 w-64" />
                  <Skeleton className="h-4 w-40" />
                </div>
              ))}
            {!isLoading &&
              (data?.unit_costs ?? []).map(([label, value]) => (
                <div key={label}>
                  <p className="font-['Inter'] text-xs text-gray-400">
                    {label}
                  </p>
                  <p className="font-['Inter'] text-sm text-gray-700">
                    {value}
                  </p>
                </div>
              ))}
          </div>
        </section>
      </div>
    </AdminLayout>
  );
}
