import type { LogLevel } from "../../hooks/usePlatformLogs";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  "data-testid"?: string;
}

function Switch({ checked, onChange, "data-testid": dataTestId }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      data-testid={dataTestId}
      onClick={() => onChange(!checked)}
      className={`
          relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full
          border-2 border-transparent transition-colors duration-200 ease-in-out
          focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2
          focus-visible:outline-none min-h-[44px]
          ${checked ? "bg-brand-primary" : "bg-gray-200"}
        `}
    >
      <span
        className={`
          pointer-events-none inline-block h-5 w-5 transform rounded-full
          bg-white shadow ring-0 transition duration-200 ease-in-out
          ${checked ? "translate-x-5" : "translate-x-0"}
        `}
      />
    </button>
  );
}

interface LogFilterBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  levelFilter: LogLevel | "";
  onLevelChange: (level: LogLevel | "") => void;
  autoScroll: boolean;
  onAutoScrollChange: (enabled: boolean) => void;
}

export function LogFilterBar({
  searchQuery,
  onSearchChange,
  levelFilter,
  onLevelChange,
  autoScroll,
  onAutoScrollChange,
}: LogFilterBarProps) {
  return (
    <div className="flex gap-3 items-center mb-3">
      {/* Search Input */}
      <div className="flex-1 bg-white border border-gray-200 rounded-xl px-4 py-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search logs..."
          className="w-full text-sm font-['Inter'] placeholder-gray-400 bg-transparent outline-none"
          data-testid="logs-search-input"
        />
      </div>

      {/* Level Filter */}
      <select
        value={levelFilter}
        onChange={(e) => onLevelChange(e.target.value as LogLevel | "")}
        className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm font-['Inter'] text-gray-600 w-36 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none min-h-[44px]"
        data-testid="logs-level-select"
      >
        <option value="">All levels</option>
        <option value="CRITICAL">CRITICAL</option>
        <option value="ERROR">ERROR</option>
        <option value="WARNING">WARNING</option>
        <option value="INFO">INFO</option>
        <option value="DEBUG">DEBUG</option>
      </select>

      {/* Auto-scroll Toggle */}
      <div className="flex items-center gap-2 text-sm font-['Inter'] text-gray-600">
        <span data-testid="logs-auto-scroll-label">Auto-scroll</span>
        <Switch
          checked={autoScroll}
          onChange={onAutoScrollChange}
          data-testid="logs-auto-scroll-toggle"
        />
      </div>
    </div>
  );
}
