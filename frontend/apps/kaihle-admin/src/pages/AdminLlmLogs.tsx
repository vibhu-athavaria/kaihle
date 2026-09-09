import { useState } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useAdminLlmLogs, LlmLogSummary } from "../hooks/useAdminLlmLogs";
import { LlmLogsTable } from "../components/llm-logs/LlmLogsTable";
import { LlmLogDetailModal } from "../components/llm-logs/LlmLogDetailModal";

const PAGE_SIZE = 50;

export function AdminLlmLogs() {
  const { logout } = useAuth();
  const [page, setPage] = useState(1);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);

  const { data, isLoading } = useAdminLlmLogs({ page, pageSize: PAGE_SIZE });

  const logs = data?.logs ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  const handleRowClick = (log: LlmLogSummary) => setSelectedLogId(log.id);

  return (
    <AdminLayout pageTitle="LLM logs" onLogout={logout}>
      <LlmLogsTable
        logs={logs}
        loading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        onRowClick={handleRowClick}
      />

      <LlmLogDetailModal
        logId={selectedLogId}
        onClose={() => setSelectedLogId(null)}
      />
    </AdminLayout>
  );
}
