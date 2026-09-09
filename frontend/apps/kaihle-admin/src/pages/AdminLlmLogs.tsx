import { useState } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  useAdminLlmLogs,
  useAdminLlmLogFilterOptions,
  LlmLogSummary,
  LlmLogSortBy,
} from "../hooks/useAdminLlmLogs";
import { LlmLogsTable } from "../components/llm-logs/LlmLogsTable";
import { LlmLogDetailModal } from "../components/llm-logs/LlmLogDetailModal";

const PAGE_SIZE = 50;

export function AdminLlmLogs() {
  const { logout } = useAuth();
  const [page, setPage] = useState(1);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [taskFilter, setTaskFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [sortBy, setSortBy] = useState<LlmLogSortBy>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const { data, isLoading } = useAdminLlmLogs({
    page,
    pageSize: PAGE_SIZE,
    task: taskFilter || undefined,
    model: modelFilter || undefined,
    sortBy,
    sortDir,
  });
  const { data: filterOptions } = useAdminLlmLogFilterOptions();

  const logs = data?.logs ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  const handleRowClick = (log: LlmLogSummary) => setSelectedLogId(log.id);

  const handleSortChange = (field: LlmLogSortBy) => {
    if (field === sortBy) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    setPage(1);
  };

  const handleTaskFilterChange = (task: string) => {
    setTaskFilter(task);
    setPage(1);
  };

  const handleModelFilterChange = (model: string) => {
    setModelFilter(model);
    setPage(1);
  };

  return (
    <AdminLayout pageTitle="LLM logs" onLogout={logout}>
      <LlmLogsTable
        logs={logs}
        loading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        onRowClick={handleRowClick}
        sortBy={sortBy}
        sortDir={sortDir}
        onSortChange={handleSortChange}
        filterOptions={filterOptions}
        taskFilter={taskFilter}
        modelFilter={modelFilter}
        onTaskFilterChange={handleTaskFilterChange}
        onModelFilterChange={handleModelFilterChange}
      />

      <LlmLogDetailModal
        logId={selectedLogId}
        onClose={() => setSelectedLogId(null)}
      />
    </AdminLayout>
  );
}
