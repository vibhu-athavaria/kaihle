interface VideoStatusBadgeProps {
  status: "pending" | "approved" | "rejected" | "stale";
  size?: "sm" | "md";
}

const STATUS_CONFIG: Record<
  string,
  { label: string; cls: string; dotCls: string }
> = {
  pending: {
    label: "Pending",
    cls: "text-brand-amber bg-brand-amber/10",
    dotCls: "bg-brand-amber",
  },
  approved: {
    label: "Approved",
    cls: "text-brand-primary bg-brand-primary/10",
    dotCls: "bg-brand-primary",
  },
  rejected: {
    label: "Rejected",
    cls: "text-red-600 bg-red-50",
    dotCls: "bg-red-500",
  },
  stale: {
    label: "Stale",
    cls: "text-gray-500 bg-gray-100",
    dotCls: "bg-gray-400",
  },
};

export function VideoStatusBadge({
  status,
  size = "md",
}: VideoStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;

  const sizeCls = size === "sm" ? "text-xs px-1.5 py-0.5" : "text-xs px-2 py-1";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium ${config.cls} ${sizeCls}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${config.dotCls}`}
      />
      {config.label}
    </span>
  );
}
