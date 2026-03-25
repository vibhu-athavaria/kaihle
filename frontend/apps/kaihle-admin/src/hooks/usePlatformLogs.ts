import { useQuery } from "@tanstack/react-query";

export type LogLevel = "CRITICAL" | "ERROR" | "WARNING" | "INFO" | "DEBUG";

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  service: string;
  message: string;
  actor?: string;
  school?: string;
  correlation_id?: string;
  extra?: Record<string, string | number | boolean | null>;
}

export interface PlatformLogsResponse {
  logs: LogEntry[];
  total: number;
}

export function usePlatformLogs(params: {
  level?: LogLevel | "";
  q?: string;
  limit?: number;
  offset?: number;
}) {
  const { level = "", q = "", limit = 100, offset = 0 } = params;

  return useQuery({
    queryKey: ["platform", "logs", { level, q, limit, offset }],
    queryFn: async () => {
      // Mock data for logs UI (no backend integration - UI stub)
      // In production, this would call GET /api/v1/platform/logs
      const mockLogs: LogEntry[] = [
        {
          id: "1",
          timestamp: "2026-03-25T13:45:00.123Z",
          level: "INFO",
          service: "api",
          message: "User authentication successful",
          actor: "teacher@greenwood.edu",
          school: "Greenwood Academy",
          correlation_id: "corr-001-abc",
          extra: { ip: "192.168.1.1", user_agent: "Mozilla/5.0" },
        },
        {
          id: "2",
          timestamp: "2026-03-25T13:44:55.456Z",
          level: "ERROR",
          service: "celery",
          message: "Failed to process gap analysis task",
          actor: "system",
          school: "Sunrise International",
          correlation_id: "corr-002-def",
          extra: {
            task_id: "gap-task-123",
            error: "TimeoutError",
            retry_count: 3,
          },
        },
        {
          id: "3",
          timestamp: "2026-03-25T13:44:30.789Z",
          level: "WARNING",
          service: "db",
          message: "Slow query detected",
          actor: "system",
          school: "Riverside School",
          correlation_id: "corr-003-ghi",
          extra: { query_ms: 2500, table: "attempts" },
        },
        {
          id: "4",
          timestamp: "2026-03-25T13:44:00.012Z",
          level: "CRITICAL",
          service: "api",
          message: "Database connection pool exhausted",
          actor: "system",
          school: undefined,
          correlation_id: "corr-004-jkl",
          extra: { pool_size: 20, active_connections: 20, waiting_threads: 15 },
        },
        {
          id: "5",
          timestamp: "2026-03-25T13:43:45.234Z",
          level: "INFO",
          service: "api",
          message: "School subscription upgraded",
          actor: "admin@kaihle.com",
          school: "Mountain View High",
          correlation_id: "corr-005-mno",
          extra: { old_tier: "STARTER", new_tier: "GROWTH" },
        },
        {
          id: "6",
          timestamp: "2026-03-25T13:43:20.567Z",
          level: "DEBUG",
          service: "api",
          message: "Cache hit for curriculum graph",
          actor: "system",
          school: "Oak Valley Prep",
          correlation_id: "corr-006-pqr",
          extra: { graph_id: "cambridge-v1", cache_ttl: 3600 },
        },
        {
          id: "7",
          timestamp: "2026-03-25T13:43:00.890Z",
          level: "ERROR",
          service: "api",
          message: "Failed to send onboarding email",
          actor: "system",
          school: "Lakewood Elementary",
          correlation_id: "corr-007-stu",
          extra: { email: "parent@example.com", error: "SMTPConnectionError" },
        },
        {
          id: "8",
          timestamp: "2026-03-25T13:42:30.123Z",
          level: "WARNING",
          service: "celery",
          message: "Task queue backlog detected",
          actor: "system",
          school: undefined,
          correlation_id: "corr-008-vwx",
          extra: { queue_name: "lesson_plan_generation", backlog_size: 150 },
        },
        {
          id: "9",
          timestamp: "2026-03-25T13:42:00.456Z",
          level: "INFO",
          service: "api",
          message: "New school created",
          actor: "admin@kaihle.com",
          school: "Harbor School",
          correlation_id: "corr-009-yza",
          extra: { school_id: "school-new-7", plan: "TRIAL" },
        },
        {
          id: "10",
          timestamp: "2026-03-25T13:41:30.789Z",
          level: "INFO",
          service: "api",
          message: "Diagnostic assessment completed",
          actor: "student@riverside.edu",
          school: "Riverside School",
          correlation_id: "corr-010-bcd",
          extra: { student_id: "student-42", score: 85, time_taken_secs: 1200 },
        },
      ];

      // Apply client-side filtering
      let filteredLogs = mockLogs;

      if (level) {
        filteredLogs = filteredLogs.filter((log) => log.level === level);
      }

      if (q) {
        const searchLower = q.toLowerCase();
        filteredLogs = filteredLogs.filter(
          (log) =>
            log.message.toLowerCase().includes(searchLower) ||
            log.service.toLowerCase().includes(searchLower) ||
            log.actor?.toLowerCase().includes(searchLower) ||
            log.school?.toLowerCase().includes(searchLower) ||
            log.correlation_id?.toLowerCase().includes(searchLower),
        );
      }

      return {
        logs: filteredLogs,
        total: filteredLogs.length,
      } as PlatformLogsResponse;
    },
    refetchInterval: 10_000, // Auto-refresh every 10 seconds
  });
}
