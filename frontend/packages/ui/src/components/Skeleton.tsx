interface SkeletonProps {
  className?: string;
  lines?: number;
}

export function Skeleton({ className = "", lines }: SkeletonProps) {
  if (lines) {
    return (
      <div className="animate-pulse space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`h-4 bg-brand-border rounded-full ${
              i === lines - 1 ? "w-2/3" : "w-full"
            }`}
          />
        ))}
      </div>
    );
  }
  return (
    <div className={`animate-pulse bg-brand-border rounded-xl ${className}`} />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-brand-border p-5 animate-pulse">
      <div className="h-4 bg-brand-border rounded-full w-1/3 mb-4" />
      <div className="h-8 bg-brand-border rounded-full w-1/2 mb-2" />
      <div className="h-3 bg-brand-border rounded-full w-2/3" />
    </div>
  );
}
