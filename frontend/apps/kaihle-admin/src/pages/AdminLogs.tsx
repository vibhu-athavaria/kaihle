import { useState, useEffect, useMemo } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { usePlatformLogs, type LogLevel } from "../hooks/usePlatformLogs";
import { LogFilterBar } from "../components/logs/LogFilterBar";
import { LogPanel } from "../components/logs/LogPanel";

export function AdminLogs() {
  const { logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState<LogLevel | "">("");
  const [autoScroll, setAutoScroll] = useState(true);

  // Debounce search input (300ms as per Pixel spec)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { data, isLoading } = usePlatformLogs({
    level: levelFilter,
    q: debouncedSearch,
    limit: 100,
    offset: 0,
  });

  const logs = useMemo(() => data?.logs ?? [], [data]);

  return (
    <AdminLayout pageTitle="System logs" onLogout={logout}>
      <div className="space-y-4">
        {/* Filter Bar */}
        <LogFilterBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          levelFilter={levelFilter}
          onLevelChange={setLevelFilter}
          autoScroll={autoScroll}
          onAutoScrollChange={setAutoScroll}
        />

        {/* Log Panel */}
        <LogPanel logs={logs} autoScroll={autoScroll} isLoading={isLoading} />
      </div>
    </AdminLayout>
  );
}
