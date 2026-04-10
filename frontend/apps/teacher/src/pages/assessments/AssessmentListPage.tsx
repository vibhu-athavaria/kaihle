import { useParams, Link } from "react-router-dom";
import { Button, Badge, EmptyState, SkeletonCard } from "@kaihle/ui";
import { toast } from "@kaihle/ui";
import { Plus, BarChart2, X } from "lucide-react";
import {
  useClassAssessments,
  useCloseAssessment,
  useDeleteAssessment,
  type AssessmentStatus,
} from "../../hooks/useClassAssessments";

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

  const {
    data: assessments,
    isLoading,
    isError,
  } = useClassAssessments(classId);

  const closeAssessment = useCloseAssessment(classId ?? "");
  const deleteAssessment = useDeleteAssessment(classId ?? "");

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
                        <button
                          type="button"
                          disabled
                          title="Results view coming soon"
                          className="flex items-center gap-1.5 text-xs font-sans font-bold text-brand-muted cursor-not-allowed px-2 py-1"
                        >
                          <BarChart2
                            className="w-3.5 h-3.5"
                            aria-hidden="true"
                          />
                          View Results
                        </button>
                      )}

                      {assessment.status === "ACTIVE" && (
                        <button
                          type="button"
                          onClick={() => handleClose(assessment.id)}
                          disabled={closeAssessment.isPending}
                          className="flex items-center gap-1.5 text-xs font-sans font-bold text-brand-body hover:text-brand-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold rounded px-2 py-1 disabled:opacity-50"
                        >
                          <X className="w-3.5 h-3.5" aria-hidden="true" />
                          Close
                        </button>
                      )}

                      {assessment.status === "DRAFT" && (
                        <button
                          type="button"
                          onClick={() => handleDelete(assessment.id)}
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
