import { Modal, Skeleton } from "@kaihle/ui";
import { useAdminLlmLogDetail } from "../../hooks/useAdminLlmLogs";
import { formatCost } from "../../utils/formatCost";

interface LlmLogDetailModalProps {
  logId: string | null;
  onClose: () => void;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400 mb-1">
        {label}
      </p>
      <p className="font-['Inter'] text-sm text-gray-700">{value}</p>
    </div>
  );
}

export function LlmLogDetailModal({ logId, onClose }: LlmLogDetailModalProps) {
  const { data: log, isLoading } = useAdminLlmLogDetail(logId);

  return (
    <Modal
      open={!!logId}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="LLM call detail"
      titleClassName="font-['Inter'] font-bold"
      maxWidth="3xl"
    >
      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {!isLoading && log && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Field label="Task" value={log.task} />
            <Field label="Model" value={log.model} />
            <Field label="Component" value={log.component ?? "—"} />
            <Field label="Run" value={log.run_id ?? "—"} />
            <Field
              label="Tokens (in/out)"
              value={`${log.prompt_tokens ?? "—"} / ${log.completion_tokens ?? "—"}`}
            />
            <Field
              label="Latency"
              value={`${log.latency_ms.toLocaleString()}ms`}
            />
            <Field label="Cost" value={formatCost(log.estimated_cost_usd)} />
            <Field
              label="Status"
              value={log.succeeded ? "OK" : (log.error_type ?? "Failed")}
            />
          </div>

          {!log.succeeded && log.error_detail && (
            <div>
              <p className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400 mb-1">
                Error detail
              </p>
              <pre className="font-['Inter'] text-sm text-red-700 bg-red-50 rounded-lg p-3 whitespace-pre-wrap break-words">
                {log.error_detail}
              </pre>
            </div>
          )}

          <div>
            <p className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400 mb-1">
              Prompt
            </p>
            <pre className="font-['Inter'] text-sm text-gray-700 bg-gray-50 rounded-lg p-3 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
              {log.prompt_text ?? "Not captured for this call."}
            </pre>
          </div>

          <div>
            <p className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400 mb-1">
              Response
            </p>
            <pre className="font-['Inter'] text-sm text-gray-700 bg-gray-50 rounded-lg p-3 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
              {log.response_text ?? "Not captured for this call."}
            </pre>
          </div>
        </div>
      )}
    </Modal>
  );
}
