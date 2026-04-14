import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { Button, Badge, EmptyState, SkeletonCard, Skeleton } from "@kaihle/ui";
import { toast } from "@kaihle/ui";
import {
  CheckCircle,
  XCircle,
  ChevronLeft,
  BookOpen,
  Edit3,
  Loader2,
} from "lucide-react";
import {
  useExplanationReviewList,
  useExplanationReviewDetail,
  useUpdateExplanation,
  type TeacherExplanationReviewItem,
} from "../../hooks/useTeacherExplanationReview";

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "pending":
      return <Badge variant="gold">Pending</Badge>;
    case "approved":
      return <Badge variant="success">Approved</Badge>;
    case "rejected":
      return <Badge variant="danger">Rejected</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

function ExplanationCard({
  item,
  onApprove,
  onReject,
}: {
  item: TeacherExplanationReviewItem;
  onApprove: (subtopicId: string) => void;
  onReject: (subtopicId: string) => void;
}) {
  return (
    <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-brand-muted" aria-hidden="true" />
          <h3 className="font-semibold text-brand-ink text-sm">
            {item.subtopic_name}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {item.has_teacher_override && (
            <Badge variant="info">Teacher Override</Badge>
          )}
          <StatusBadge status={item.review_status} />
        </div>
      </div>

      {item.explanation_text && (
        <p className="text-xs text-brand-body mb-4 line-clamp-3">
          {item.explanation_text}
        </p>
      )}

      {item.teacher_explanation && (
        <div className="bg-brand-surface rounded-lg p-3 mb-4">
          <p className="text-xs text-brand-muted font-medium mb-1">
            Your Override:
          </p>
          <p className="text-xs text-brand-ink">{item.teacher_explanation}</p>
        </div>
      )}

      {item.review_status === "pending" && (
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            className="gap-1 bg-brand-success hover:bg-emerald-600"
            onClick={() => onApprove(item.subtopic_id)}
          >
            <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />
            Approve
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="gap-1"
            onClick={() => onReject(item.subtopic_id)}
          >
            <XCircle className="w-3.5 h-3.5" aria-hidden="true" />
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}

function DetailPanel({
  classId,
  subtopicId,
  onBack,
}: {
  classId: string;
  subtopicId: string;
  onBack: () => void;
}) {
  const { data, isLoading, isError } = useExplanationReviewDetail(
    classId,
    subtopicId,
  );
  const updateExplanation = useUpdateExplanation();
  const [showOverrideEditor, setShowOverrideEditor] = useState(false);
  const [overrideText, setOverrideText] = useState("");

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="text-center py-12 text-brand-muted">
        Failed to load explanation detail.
      </div>
    );
  }

  function handleApprove() {
    updateExplanation.mutate(
      { classId, subtopicId, body: { review_status: "approved" } },
      {
        onSuccess: () => toast.success("Explanation approved."),
        onError: () => toast.error("Failed to approve explanation."),
      },
    );
  }

  function handleReject() {
    updateExplanation.mutate(
      { classId, subtopicId, body: { review_status: "rejected" } },
      {
        onSuccess: () => toast.success("Explanation rejected."),
        onError: () => toast.error("Failed to reject explanation."),
      },
    );
  }

  function handleAddOverride() {
    if (!overrideText.trim()) return;
    updateExplanation.mutate(
      {
        classId,
        subtopicId,
        body: { teacher_explanation: overrideText.trim() },
      },
      {
        onSuccess: () => {
          toast.success("Teacher override added.");
          setShowOverrideEditor(false);
          setOverrideText("");
        },
        onError: () => toast.error("Failed to add override."),
      },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-1.5 hover:bg-brand-surface rounded-lg transition-colors"
          aria-label="Back to list"
        >
          <ChevronLeft className="w-5 h-5 text-brand-muted" />
        </button>
        <div>
          <h2 className="text-lg font-semibold text-brand-ink">
            {data.subtopic_name}
          </h2>
          <p className="text-xs text-brand-muted">{data.learning_objective}</p>
        </div>
      </div>

      <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="font-semibold text-brand-ink text-sm">
            AI Explanation
          </h3>
          <StatusBadge status={data.review_status} />
        </div>
        {data.explanation_text ? (
          <p className="text-sm text-brand-body leading-relaxed">
            {data.explanation_text}
          </p>
        ) : (
          <p className="text-sm text-brand-muted italic">
            No AI explanation available.
          </p>
        )}
      </div>

      {data.teacher_explanation && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Edit3 className="w-4 h-4 text-brand-muted" aria-hidden="true" />
            <h3 className="font-semibold text-brand-ink text-sm">
              Your Override Explanation
            </h3>
          </div>
          <p className="text-sm text-brand-body leading-relaxed">
            {data.teacher_explanation}
          </p>
        </div>
      )}

      {!showOverrideEditor && !data.teacher_explanation && (
        <Button
          variant="secondary"
          size="sm"
          className="gap-1"
          onClick={() => setShowOverrideEditor(true)}
        >
          <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
          Add Teacher Override
        </Button>
      )}

      {showOverrideEditor && (
        <div className="bg-white border border-brand-border rounded-xl p-5 shadow-sm">
          <h3 className="font-semibold text-brand-ink text-sm mb-3">
            Write Your Override Explanation
          </h3>
          <textarea
            className="w-full border border-brand-border rounded-lg p-3 text-sm text-brand-ink placeholder:text-brand-muted focus:outline-none focus:ring-2 focus:ring-brand-primary/30 resize-y min-h-32"
            placeholder="Write your own explanation to override the AI explanation..."
            value={overrideText}
            onChange={(e) => setOverrideText(e.target.value)}
            maxLength={5000}
          />
          <div className="flex items-center gap-2 mt-3">
            <Button
              variant="primary"
              size="sm"
              className="gap-1"
              onClick={handleAddOverride}
              disabled={!overrideText.trim() || updateExplanation.isPending}
            >
              {updateExplanation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle className="w-3.5 h-3.5" />
              )}
              Save Override
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowOverrideEditor(false);
                setOverrideText("");
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {data.review_status === "pending" && (
        <div className="flex items-center gap-2 pt-2">
          <Button
            variant="primary"
            size="sm"
            className="gap-1 bg-brand-success hover:bg-emerald-600"
            onClick={handleApprove}
            disabled={updateExplanation.isPending}
          >
            {updateExplanation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5" />
            )}
            Approve
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="gap-1"
            onClick={handleReject}
            disabled={updateExplanation.isPending}
          >
            <XCircle className="w-3.5 h-3.5" aria-hidden="true" />
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}

export function ExplanationReviewPage() {
  const { classId } = useParams<{ classId: string }>();
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data: dashboardData } = useTeacherDashboard(schoolId);
  const currentClass = dashboardData?.classes.find((c) => c.id === classId);
  const [statusFilter, setStatusFilter] = useState<string | null>("pending");
  const [selectedSubtopicId, setSelectedSubtopicId] = useState<string | null>(
    null,
  );
  const updateExplanation = useUpdateExplanation();

  const { data, isLoading, isError } = useExplanationReviewList(
    classId ?? "",
    statusFilter,
  );

  function handleApprove(subtopicId: string) {
    if (!classId) return;
    updateExplanation.mutate(
      { classId, subtopicId, body: { review_status: "approved" } },
      {
        onSuccess: () => toast.success("Explanation approved."),
        onError: () => toast.error("Failed to approve."),
      },
    );
  }

  function handleReject(subtopicId: string) {
    if (!classId) return;
    updateExplanation.mutate(
      { classId, subtopicId, body: { review_status: "rejected" } },
      {
        onSuccess: () => toast.success("Explanation rejected."),
        onError: () => toast.error("Failed to reject."),
      },
    );
  }

  if (!classId) {
    return (
      <div className="text-center py-12 text-brand-muted">
        No class selected.
      </div>
    );
  }

  if (selectedSubtopicId) {
    return (
      <DetailPanel
        classId={classId}
        subtopicId={selectedSubtopicId}
        onBack={() => setSelectedSubtopicId(null)}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav
        className="flex items-center gap-2 text-sm text-brand-muted"
        aria-label="Breadcrumb"
      >
        <Link
          to="/teacher/classes"
          className="hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
        >
          Classes
        </Link>
        <span className="text-brand-border" aria-hidden="true">
          /
        </span>
        <Link
          to={`/teacher/classes/${classId}`}
          className="hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold rounded"
        >
          {currentClass?.name ?? "Class"}
        </Link>
        <span className="text-brand-border" aria-hidden="true">
          /
        </span>
        <span className="text-brand-ink font-medium">Content Review</span>
      </nav>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            Content Review
          </h1>
          <p className="text-sm text-brand-muted mt-0.5">
            Review and approve AI-generated explanations for your class
          </p>
        </div>
        {data && data.pending_count > 0 && (
          <Badge variant="gold">{data.pending_count} pending review</Badge>
        )}
      </div>

      <div className="flex items-center gap-2">
        {[
          { value: null, label: "All" },
          { value: "pending", label: "Pending" },
          { value: "approved", label: "Approved" },
          { value: "rejected", label: "Rejected" },
        ].map((filter) => (
          <button
            key={filter.label}
            onClick={() => setStatusFilter(filter.value)}
            className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
              statusFilter === filter.value
                ? "bg-brand-primary text-white"
                : "bg-brand-surface text-brand-muted hover:bg-brand-border"
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {isError && (
        <div className="text-center py-12">
          <p className="text-brand-muted">Failed to load explanations.</p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          emoji="📚"
          title="No explanations to review"
          description={
            statusFilter === "pending"
              ? "All explanations have been reviewed."
              : "No explanations match the selected filter."
          }
        />
      )}

      {data && data.items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.items.map((item) => (
            <button
              key={item.subtopic_content_id}
              onClick={() => setSelectedSubtopicId(item.subtopic_id)}
              className="text-left w-full"
            >
              <ExplanationCard
                item={item}
                onApprove={(id) => {
                  handleApprove(id);
                }}
                onReject={(id) => {
                  handleReject(id);
                }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
