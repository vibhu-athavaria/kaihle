// UI: "Content Review" | Route: /teacher/content-review | API: /explanation-review
// All three are intentional — do not rename.

import { useState, useMemo } from "react";
import { useAuth } from "@kaihle/auth";
import { useTeacherClasses } from "../../hooks/useTeacherClasses";
import { useAllTeacherExplanationReview, type TeacherReviewStatus } from "../../hooks/useTeacherExplanationReview";
import { Badge, EmptyState, SkeletonCard } from "@kaihle/ui";
import { CheckCircle, XCircle } from "lucide-react";

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

  const { data: classes = [], isLoading: classesLoading } = useTeacherClasses(
    schoolId,
    false
  );

  const [statusFilter, setStatusFilter] = useState<FilterStatus>("PENDING");
  const [classFilter, setClassFilter] = useState<string | null>(null);

  const { data: items = [], isLoading: itemsLoading } =
    useAllTeacherExplanationReview(
      statusFilter === "all" ? undefined : statusFilter as TeacherReviewStatus
    );

  const isLoading = classesLoading || itemsLoading;

  const allItems = useMemo(() => {
    return [...items].sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
  }, [items]);

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
              key={item.subtopicContentId}
              className="bg-white rounded-2xl border border-brand-border p-5"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {statusBadge(item.reviewStatus)}
                    <span className="text-xs text-brand-muted">
                      {item.className}
                    </span>
                  </div>
                  <h3 className="font-display font-semibold text-brand-ink">
                    {item.subtopicName}
                  </h3>
                </div>
                <span className="text-xs text-brand-muted whitespace-nowrap">
                  {new Date(item.createdAt).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              </div>

              <p className="text-sm text-brand-body leading-relaxed mb-4">
                {item.explanationText}
              </p>

              {item.reviewStatus === "PENDING" && (
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
