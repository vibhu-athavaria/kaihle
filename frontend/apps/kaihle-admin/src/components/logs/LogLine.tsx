import { useState } from "react";
import type { LogEntry } from "../../hooks/usePlatformLogs";

interface LogLineProps {
  log: LogEntry;
}

const levelColors: Record<string, string> = {
  CRITICAL: "text-red-300",
  ERROR: "text-red-400",
  WARNING: "text-amber-400",
  INFO: "text-green-400",
  DEBUG: "text-slate-500",
};

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toISOString().replace("T", " ").replace("Z", "");
}

/**
 * Sanitize a string to prevent XSS attacks.
 * Escapes HTML special characters to render user-provided content safely.
 */
function sanitizeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

export function LogLine({ log }: LogLineProps) {
  const [expanded, setExpanded] = useState(false);
  const hasExtra = log.extra && Object.keys(log.extra).length > 0;

  const handleClick = () => {
    if (hasExtra) {
      setExpanded(!expanded);
    }
  };

  return (
    <div>
      <div
        onClick={handleClick}
        className={`
          flex items-start gap-3 py-1.5
          ${hasExtra ? "hover:bg-slate-800 rounded cursor-pointer" : ""}
          transition-colors duration-75
        `}
        data-testid={`log-line-${log.id}`}
        data-level={log.level}
      >
        {/* Timestamp */}
        <span
          className="font-mono text-[11px] text-slate-500 w-48 flex-shrink-0 tabular-nums"
          data-testid={`log-timestamp-${log.id}`}
        >
          {formatTimestamp(log.timestamp)}
        </span>

        {/* Level badge */}
        <span
          className={`font-mono text-[11px] font-bold w-12 flex-shrink-0 ${
            levelColors[log.level]
          }`}
          data-testid={`log-level-${log.id}`}
        >
          {log.level}
        </span>

        {/* Service */}
        <span
          className="font-mono text-[11px] text-blue-400 w-24 flex-shrink-0"
          data-testid={`log-service-${log.id}`}
        >
          {log.service}
        </span>

        {/* Message */}
        <span
          className={`font-mono text-[12px] flex-1 break-words ${
            levelColors[log.level]
          }`}
          data-testid={`log-message-${log.id}`}
        >
          {sanitizeHtml(log.message)}
        </span>
      </div>

      {/* Expandable extra fields */}
      {expanded && hasExtra && (
        <div
          className="bg-slate-950 text-slate-300 text-[11px] font-mono p-3 mt-1 rounded whitespace-pre-wrap"
          data-testid={`log-extra-${log.id}`}
        >
          {JSON.stringify(log.extra, null, 2)}
        </div>
      )}
    </div>
  );
}
