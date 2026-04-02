import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { ConfigSection } from "../components/config/ConfigSection";
import { ConfigRow } from "../components/config/ConfigRow";

interface PlatformConfig {
  llm_provider: string;
  runpod_status: "active" | "blocked" | "error";
  trial_days: number;
  trial_students_limit: number;
  rate_limit_requests_per_minute: number;
  rate_limit_concurrent_users: number;
}

function usePlatformConfig() {
  return useQuery({
    queryKey: ["platform", "config"],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/platform/stats");
      return response.data as PlatformConfig;
    },
  });
}

export function AdminConfig() {
  const { logout } = useAuth();
  const { data: config, isLoading } = usePlatformConfig();

  return (
    <AdminLayout pageTitle="Platform config" onLogout={logout}>
      <div className="space-y-4">
        <ConfigSection title="LLM Provider">
          <ConfigRow
            label="Active Provider"
            value={isLoading ? undefined : (config?.llm_provider ?? "—")}
            valueClassName="font-mono text-sm"
          />
          <ConfigRow
            label="RunPod Status"
            badge={
              config?.runpod_status === "blocked"
                ? { text: "Blocked", variant: "red" as const }
                : config?.runpod_status === "active"
                  ? { text: "Active", variant: "green" as const }
                  : { text: "Error", variant: "amber" as const }
            }
            isLast
            testId="runpod-status"
          />
        </ConfigSection>

        <ConfigSection title="Trial Settings">
          <ConfigRow
            label="Default Trial Length"
            value={isLoading ? undefined : `${config?.trial_days ?? "—"} days`}
          />
          <ConfigRow
            label="Max Trial Students"
            value={
              isLoading ? undefined : (config?.trial_students_limit ?? "—")
            }
          />
        </ConfigSection>

        <ConfigSection title="Rate Limits">
          <ConfigRow
            label="Requests per Minute"
            value={
              isLoading
                ? undefined
                : (config?.rate_limit_requests_per_minute ?? "—")
            }
          />
          <ConfigRow
            label="Concurrent Users"
            value={
              isLoading
                ? undefined
                : (config?.rate_limit_concurrent_users ?? "—")
            }
            isLast
          />
        </ConfigSection>
      </div>
    </AdminLayout>
  );
}
