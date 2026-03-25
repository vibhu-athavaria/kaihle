import { useEffect, useRef } from "react";
import type { LogEntry } from "../../hooks/usePlatformLogs";
import { LogLine } from "./LogLine";

interface LogPanelProps {
  logs: LogEntry[];
  autoScroll: boolean;
  isLoading?: boolean;
}

export function LogPanel({ logs, autoScroll, isLoading }: LogPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && panelRef.current) {
      panelRef.current.scrollTop = panelRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      {/* Panel Header */}
      <div className="bg-slate-800 px-4 py-2 flex items-center gap-2">
        {/* Traffic light dots */}
        <div className="flex gap-1.5">
          <div
            className="w-3 h-3 rounded-full bg-red-400/60"
            aria-label="close"
          />
          <div
            className="w-3 h-3 rounded-full bg-amber-400/60"
            aria-label="minimize"
          />
          <div
            className="w-3 h-3 rounded-full bg-green-400/60"
            aria-label="maximize"
          />
        </div>
        {/* Title */}
        <span className="font-mono text-xs text-slate-400">
          kaihle-platform-logs
        </span>
      </div>

      {/* Panel Body */}
      <div
        ref={panelRef}
        className="bg-slate-900 h-[560px] overflow-y-auto px-4 py-3 md:h-[360px]"
        data-testid="log-panel-body"
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <span className="font-mono text-sm text-slate-500">
              Loading logs...
            </span>
          </div>
        ) : logs.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <span className="font-mono text-sm text-slate-500">
              No logs found
            </span>
          </div>
        ) : (
          <div className="space-y-0">
            {logs.map((log) => (
              <LogLine key={log.id} log={log} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
