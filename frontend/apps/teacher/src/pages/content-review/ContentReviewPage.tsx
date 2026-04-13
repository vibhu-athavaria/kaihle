// UI: "Content Review" | Route: /teacher/content-review | API: /explanation-review
// All three are intentional — do not rename.

import { useState, useMemo } from "react";
import { useAuth } from "@kaihle/auth";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { apiClient } from "@kaihle/auth";
import { useQueries } from "@tanstack/react-query";
import { Badge, EmptyState, SkeletonCard } from "@kaihle/ui";
import { CheckCircle, XCircle } from "lucide-react";

interface ReviewItem {
  id: string;
  subtopic_name: string;
  explanation_text: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  created_at: string;
  className: string;
  classId: string;
}

type FilterStatus = "PENDING" | "APPROVED" | "REJECTED" | "all";

function statusBadge(status: string) {
  switch (status) {
    case "PENDING":
      return <Badge variant="gold">Pending</Badge>;
    case "APPROVED":
      return <Badge variant="success">Approved</Badge>;
    case "REJECTED":
      return <Badge variant="danger">Rejected</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

export function ContentReviewPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data: dashboardData, isLoading: dashboardLoading } =
    useTeacherDashboard(schoolId);

  const classes = dashboardData?.classes ?? [];
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("PENDING");
  const [classFilter, setClassFilter] = useState<string | null>(null);

  const reviewQueries = useQueries({
    queries: classes.map((cls) => ({
      queryKey: ["explanation-review", cls.id, statusFilter],
      queryFn: async () => {
        const params =
          statusFilter !== "all" ? `?status=${statusFilter.toLowerCase()}` : "";
        const res = await apiClient
          .get(
            `/api/v1/teacher/classes/${cls.id}/explanation-review${params}`,
          )
          .catch(() => ({ data: { data: [] } }));
        const items = res.data.data ?? res.data ?? [];
        return items.map((item: ReviewItem) => ({
          ...item,
          className: cls.name,
          classId: cls.id,
        }));
      },
      enabled: classes.length > 0,
    })),
  });

  const isLoading =
    dashboardLoading || reviewQueries.some((q) => q.isPending);

  const allItems = useMemo(() => {
    const result: ReviewItem[] = [];
    reviewQueries.forEach((q) => {
      if (q.data) result.push(...(q.data as ReviewItem[]));
    });
    return result.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, [reviewQueries]);

  const filteredItems = useMemo(() => {
    if (!classFilter) return allItems;
    return allItems.filter((item) => item.classId === classFilter);
  }, [allItems, classFilter]);

  const filterButtons: { label: string; value: FilterStatus }[] = [
    { label: "Pending", value: "PENDING" },
    { label: "Approved", value: "APPROVED" },
    { label: "Rejected", value: "REJECTED" },
    { label: "All", value: "all" },
  ];

  return (
    <div className="p-6 space-y-6">
      <h1 className="font-display font-bold text-2xl text-brand-ink">
        Content Review
      </h1>

      {/* Status filter chips */}
      <div className="flex items-center gap-2 flex-wrap">
        {filterButtons.map((btn) => (
          <button
            key={btn.value}
            type="button"
            onClick={() => setStatusFilter(btn.value)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
              statusFilter === btn.value
                ? "bg-brand-primary text-white"
                : "bg-white border border-brand-border text-brand-body hover:text-brand-ink"
            }`}
          >
            {btn.label}
          </button>
        ))}

        {/* Class filter chips */}
        {classes.length > 1 && (
          <>
            <span className="text-brand-border mx-1" aria-hidden="true">
              |
            </span>
            <button
              type="button"
              onClick={() => setClassFilter(null)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
                classFilter === null
                  ? "bg-brand-ink text-white"
                  : "bg-white border border-brand-border text-brand-body hover:text-brand-ink"
              }`}
            >
              All classes
            </button>
            {classes.map((cls) => (
              <button
                key={cls.id}
                type="button"
                onClick={() => setClassFilter(cls.id)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
                  classFilter === cls.id
                    ? "bg-brand-ink text-white"
                    : "bg-white border border-brand-border text-brand-body hover:text-brand-ink"
                }`}
              >
                {cls.name}
              </button>
            ))}
          </>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : filteredItems.length === 0 ? (
        <EmptyState
          emoji="✅"
          title="Nothing to review"
          description={
            statusFilter === "PENDING"
              ? "All AI-generated explanations are up to date."
              : "No items match this filter."
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-2xl border border-brand-border p-5"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {statusBadge(item.status)}
                    <span className="text-xs text-brand-muted">
                      {item.className}
                    </span>
                  </div>
                  <h3 className="font-display font-semibold text-brand-ink">
                    {item.subtopic_name}
                  </h3>
                </div>
                <span className="text-xs text-brand-muted whitespace-nowrap">
                  {new Date(item.created_at).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              </div>

              <p className="text-sm text-brand-body leading-relaxed mb-4">
                {item.explanation_text}
              </p>

              {item.status === "PENDING" && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-primary border border-brand-mid rounded-full hover:bg-brand-light transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                  >
                    <CheckCircle className="w-4 h-4" aria-hidden="true" />
                    Approve
                  </button>
                  <button
                    type="button"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-red border border-brand-red/30 rounded-full hover:bg-brand-red-light transition-colors focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2"
                  >
                    <XCircle className="w-4 h-4" aria-hidden="true" />
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
