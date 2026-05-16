import { useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { Button, Badge, EmptyState, SkeletonCard } from "@kaihle/ui";
import { toast } from "@kaihle/ui";
import { Plus, BarChart2, X } from "lucide-react";
import {
  useClassAssessments,
  useCloseAssessment,
  useDeleteAssessment,
  type AssessmentStatus,
} from "../../hooks/useClassAssessments";
import { useClass } from "../../hooks/useClass";

function statusBadge(status: AssessmentStatus) {
  switch (status) {
    case "DRAFT":
      return <Badge variant="neutral">Draft</Badge>;
    case "ACTIVE":
      return <Badge variant="success">Active</Badge>;
    case "CLOSED":
      return <Badge variant="info">Closed</Badge>;
  }
}

function typeBadge(type: string) {
  const label = type
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return <Badge variant="gold">{label}</Badge>;
}

export function AssessmentListPage() {
  const { classId } = useParams<{ classId: string }>();
  const [searchParams] = useSearchParams();
  const [dismissedBanner, setDismissedBanner] = useState(false);

  const { data: currentClass } = useClass(classId);

  const {
    data: assessments,
    isLoading,
    isError,
  } = useClassAssessments(classId);

  const closeAssessment = useCloseAssessment(classId ?? "");
  const deleteAssessment = useDeleteAssessment(classId ?? "");

  const justPublished = searchParams.get("published") === "true";
  const showBanner = justPublished && !dismissedBanner;

  function handleClose(assessmentId: string) {
    closeAssessment.mutate(assessmentId, {
      onSuccess: () => toast.success("Assessment closed."),
      onError: () => toast.error("Failed to close assessment."),
    });
  }

  function handleDelete(assessmentId: string) {
    deleteAssessment.mutate(assessmentId, {
      onSuccess: () => toast.success("Assessment deleted."),
      onError: () => toast.error("Failed to delete assessment."),
    });
  }

  return (
    <div className="p-6">
      {classId && (
        <nav
          className="flex items-center gap-2 text-sm text-brand-muted mb-4"
          aria-label="Breadcrumb"
        >
          <Link
            to="/teacher/classes"
            className="hover:text-brand-ink transition-colors"
          >
            Classes
          </Link>
          <span aria-hidden="true">/</span>
          <Link
            to={`/teacher/classes/${classId}`}
            className="hover:text-brand-ink transition-colors"
          >
            {currentClass?.name ?? "Class"}
          </Link>
          <span aria-hidden="true">/</span>
          <span className="text-brand-ink font-medium">Assessments</span>
        </nav>
      )}

      {showBanner && (
        <div className="bg-brand-green-light border border-brand-green rounded-xl p-4 flex items-center justify-between mb-4">
          <span className="text-sm font-medium text-brand-ink">
            ✓ Assessment published — students can now complete it.
          </span>
          <button
            type="button"
            onClick={() => setDismissedBanner(true)}
            className="text-brand-muted hover:text-brand-ink transition-colors"
            aria-label="Dismiss success banner"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Assessments
        </h1>
        <Link to="/teacher/assessments/new">
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
            icon={<Plus className="w-4 h-4" aria-hidden="true" />}
          >
            Create New Assessment
          </Button>
        </Link>
      </div>

      {isError && (
        <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4 mb-4">
          <p className="text-sm font-sans text-brand-red">
            Failed to load assessments. Please try again.
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : assessments && assessments.length === 0 ? (
        <EmptyState
          emoji="📋"
          title="No assessments yet"
          description="Create your first assessment to see student progress."
          action={
            <Link to="/teacher/assessments/new">
              <Button
                variant="primary"
                className="bg-brand-gold hover:bg-brand-gold-dark"
              >
                Create Assessment
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="bg-white rounded-2xl border border-brand-border overflow-hidden shadow-card">
          <table className="w-full" aria-label="Assessments list">
            <thead>
              <tr className="border-b border-brand-border bg-brand-border-soft">
                <th className="text-left px-5 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Title
                </th>
                <th className="text-left px-4 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Status
                </th>
                <th className="text-center px-4 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Questions
                </th>
                <th className="text-left px-4 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Deadline
                </th>
                <th className="text-right px-5 py-3 text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border-soft">
              {assessments?.map((assessment) => (
                <tr
                  key={assessment.id}
                  className="hover:bg-brand-border-soft/50 transition-colors"
                >
                  <td className="px-5 py-4">
                    <span className="text-sm font-sans font-medium text-brand-ink">
                      {assessment.title}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    {typeBadge(assessment.assessment_type)}
                  </td>
                  <td className="px-4 py-4">
                    {statusBadge(assessment.status)}
                  </td>
                  <td className="px-4 py-4 text-center">
                    <span className="text-sm font-sans text-brand-body">
                      {assessment.question_count}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <span className="text-sm font-sans text-brand-body">
                      {assessment.deadline
                        ? new Date(assessment.deadline).toLocaleDateString(
                            "en-GB",
                            { day: "numeric", month: "short", year: "numeric" },
                          )
                        : "—"}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center justify-end gap-2">
                      {(assessment.status === "ACTIVE" ||
                        assessment.status === "CLOSED") && (
                        <Link
                          to={`/teacher/assessments/${assessment.id}/results`}
                          className="flex items-center gap-1.5 text-xs font-sans font-bold text-brand-muted hover:text-brand-ink transition-colors px-2 py-1"
                        >
                          <BarChart2
                            className="w-3.5 h-3.5"
                            aria-hidden="true"
                          />
                          View Results
                        </Link>
                      )}

                      {assessment.status === "ACTIVE" &&
                        assessment.attempt_count > 0 && (
                          <button
                            type="button"
                            onClick={() => handleClose(assessment.id)}
                            disabled={closeAssessment.isPending}
                            className="flex items-center gap-1.5 text-xs font-sans font-bold text-brand-body hover:text-brand-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded px-2 py-1 disabled:opacity-50"
                          >
                            <X className="w-3.5 h-3.5" aria-hidden="true" />
                            Archive
                          </button>
                        )}

                      {(assessment.status === "DRAFT" ||
                        (assessment.status === "ACTIVE" &&
                          assessment.attempt_count === 0)) && (
                        <button
                          type="button"
                          onClick={() => {
                            if (
                              assessment.status === "ACTIVE" &&
                              !window.confirm(
                                "Delete this assessment? Students won't be able to access it.",
                              )
                            )
                              return;
                            handleDelete(assessment.id);
                          }}
                          disabled={deleteAssessment.isPending}
                          className="flex items-center gap-1.5 text-xs font-sans font-bold text-brand-red hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded px-2 py-1 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
