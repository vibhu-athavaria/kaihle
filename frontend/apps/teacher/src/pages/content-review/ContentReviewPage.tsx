// UI: "Content Review" | Route: /teacher/content-review | API: /explanation-review
// All three are intentional — do not rename.

import { useState, useMemo } from "react";
import { useAuth } from "@kaihle/auth";
import { useTeacherClasses } from "../../hooks/useTeacherClasses";
import {
  useAllTeacherExplanationReview,
  useUpdateExplanation,
  type TeacherReviewStatus,
  type TeacherExplanationReviewWithClass,
} from "../../hooks/useTeacherExplanationReview";
import { Badge, EmptyState, Modal, SkeletonCard } from "@kaihle/ui";
import { CheckCircle, ThumbsUp, XCircle } from "lucide-react";

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

function QualityBadge({
  thumbsUpCount,
  thumbsDownCount,
}: {
  thumbsUpCount: number;
  thumbsDownCount: number;
}) {
  const total = thumbsUpCount + thumbsDownCount;

  if (total === 0) {
    return (
      <span className="text-xs text-brand-muted flex items-center gap-1">
        <ThumbsUp className="w-3 h-3" aria-hidden="true" />
        No feedback yet
      </span>
    );
  }

  const pct = Math.round((thumbsUpCount / total) * 100);

  let qualityClass = "";
  let qualityLabel = "";
  if (pct >= 70) {
    qualityClass =
      "bg-brand-green-light text-brand-green border border-brand-green/20";
    qualityLabel = "Good";
  } else if (pct >= 40) {
    qualityClass =
      "bg-brand-amber-light text-brand-amber border border-brand-amber/20";
    qualityLabel = "Mixed";
  } else {
    qualityClass =
      "bg-brand-red-light text-brand-red border border-brand-red/20";
    qualityLabel = "Poor";
  }

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-brand-muted flex items-center gap-1">
        <ThumbsUp className="w-3 h-3" aria-hidden="true" />
        {pct}%
      </span>
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${qualityClass}`}
      >
        {qualityLabel}
      </span>
    </div>
  );
}

function RejectModal({
  item,
  open,
  onOpenChange,
}: {
  item: TeacherExplanationReviewWithClass;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [note, setNote] = useState("");
  const updateMutation = useUpdateExplanation();

  function handleReject() {
    updateMutation.mutate(
      {
        classId: item.classId,
        subtopicId: item.subtopicId,
        body: {
          review_status: "rejected",
          ...(note.trim() ? { teacher_note: note.trim() } : {}),
        },
      },
      {
        onSuccess: () => {
          setNote("");
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Reject explanation">
      <div className="space-y-4">
        <p className="text-sm text-brand-body">
          Rejecting:{" "}
          <span className="font-semibold text-brand-ink">
            {item.subtopicName}
          </span>
        </p>
        <div className="space-y-1.5">
          <label
            htmlFor="teacher-note"
            className="block text-sm font-medium text-brand-ink"
          >
            Rejection note{" "}
            <span className="text-brand-muted font-normal">(optional)</span>
          </label>
          <textarea
            id="teacher-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            maxLength={1000}
            placeholder="Explain why this explanation is being rejected..."
            className="w-full rounded-lg border border-brand-border px-3 py-2 text-sm text-brand-ink placeholder:text-brand-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 resize-none"
          />
          <p className="text-xs text-brand-muted text-right">
            {note.length}/1000
          </p>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 text-sm font-medium text-brand-ink border border-brand-border rounded-full hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleReject}
            disabled={updateMutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-brand-red rounded-full hover:bg-brand-red/90 disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2"
          >
            <XCircle className="w-4 h-4" aria-hidden="true" />
            {updateMutation.isPending ? "Rejecting…" : "Reject"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function ExplanationCard({
  item,
}: {
  item: TeacherExplanationReviewWithClass;
}) {
  const [rejectOpen, setRejectOpen] = useState(false);
  const updateMutation = useUpdateExplanation();

  function handleApprove() {
    updateMutation.mutate({
      classId: item.classId,
      subtopicId: item.subtopicId,
      body: { review_status: "approved" },
    });
  }

  return (
    <>
      <div className="bg-white rounded-2xl border border-brand-border p-5">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              {statusBadge(item.reviewStatus)}
              <span className="text-xs text-brand-muted">{item.className}</span>
            </div>
            <h3 className="font-display font-semibold text-brand-ink">
              {item.subtopicName}
            </h3>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <span className="text-xs text-brand-muted whitespace-nowrap">
              {new Date(item.createdAt).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </span>
            <QualityBadge
              thumbsUpCount={item.thumbsUpCount}
              thumbsDownCount={item.thumbsDownCount}
            />
          </div>
        </div>

        <p className="text-sm text-brand-body leading-relaxed mb-4">
          {item.explanationText}
        </p>

        {item.reviewStatus === "PENDING" && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleApprove}
              disabled={updateMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-gold border border-brand-gold/30 rounded-full hover:bg-brand-gold/5 disabled:opacity-60 transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
            >
              <CheckCircle className="w-4 h-4" aria-hidden="true" />
              {updateMutation.isPending &&
              updateMutation.variables?.body?.review_status === "approved"
                ? "Approving…"
                : "Approve"}
            </button>
            <button
              type="button"
              onClick={() => setRejectOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-red border border-brand-red/30 rounded-full hover:bg-brand-red-light transition-colors focus-visible:ring-2 focus-visible:ring-brand-red focus-visible:ring-offset-2"
            >
              <XCircle className="w-4 h-4" aria-hidden="true" />
              Reject
            </button>
          </div>
        )}
      </div>

      <RejectModal item={item} open={rejectOpen} onOpenChange={setRejectOpen} />
    </>
  );
}

export function ContentReviewPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;

  const { data: classes = [], isLoading: classesLoading } = useTeacherClasses(
    schoolId,
    false,
  );

  const [statusFilter, setStatusFilter] = useState<FilterStatus>("PENDING");
  const [classFilter, setClassFilter] = useState<string | null>(null);

  const { data: items = [], isLoading: itemsLoading } =
    useAllTeacherExplanationReview(
      statusFilter === "all"
        ? undefined
        : (statusFilter as TeacherReviewStatus),
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
                ? "bg-brand-gold text-white"
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
            <ExplanationCard key={item.subtopicContentId} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
