import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { useClassAssessments } from "../../hooks/useClassAssessments";
import { statusBadge, typeBadge, type Assessment, type AssessmentStatus } from "../../utils/assessment";
import { BarChart2 } from "lucide-react";
import { Button, EmptyState, SkeletonCard } from "@kaihle/ui";

interface AssessmentWithClass extends Assessment {
  className: string;
  classId: string;
}

export function AllAssessmentsPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data: dashboardData, isLoading: dashboardLoading } =
    useTeacherDashboard(schoolId);

  const classes = dashboardData?.classes ?? [];
  const classAssessments = classes.map((cls) =>
    useClassAssessments(cls.id),
  );

  const [filter, setFilter] = useState<"all" | AssessmentStatus>("all");

  const allAssessments = useMemo(() => {
    const result: AssessmentWithClass[] = [];
    classAssessments.forEach((query, i) => {
      if (query.data) {
        for (const a of query.data) {
          result.push({
            ...a,
            className: classes[i].name,
            classId: classes[i].id,
          });
        }
      }
    });
    return result;
  }, [classAssessments, classes]);

  const filtered = useMemo(() => {
    if (filter === "all") return allAssessments;
    return allAssessments.filter((a) => a.status === filter);
  }, [allAssessments, filter]);

  const isLoading =
    dashboardLoading || classAssessments.some((q) => q.isLoading);

  const filters: { key: "all" | AssessmentStatus; label: string }[] = [
    { key: "all", label: "All" },
    { key: "ACTIVE", label: "Active" },
    { key: "DRAFT", label: "Draft" },
    { key: "CLOSED", label: "Closed" },
  ];

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            Assessments
          </h1>
          <Link to="/teacher/assessments/new">
            <Button
              variant="primary"
              className="bg-brand-gold hover:bg-brand-gold-dark"
            >
              New Assessment
            </Button>
          </Link>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Assessments
        </h1>
        <Link to="/teacher/assessments/new">
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
          >
            New Assessment
          </Button>
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {filters.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === f.key
                ? "bg-brand-gold text-white"
                : "bg-white border border-brand-border text-brand-muted hover:text-brand-ink"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          emoji="📋"
          title="No assessments found"
          description={
            filter === "all"
              ? "Create your first assessment to get started."
              : `No ${filter.toLowerCase()} assessments.`
          }
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
        <div className="space-y-3">
          {filtered.map((assessment) => (
            <div
              key={assessment.id}
              className="bg-white rounded-xl border border-brand-border p-4 flex items-center justify-between"
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-brand-ink">
                    {assessment.title}
                  </span>
                  {typeBadge(assessment.assessment_type)}
                  {statusBadge(assessment.status)}
                </div>
                <div className="text-xs text-brand-muted">
                  {assessment.className} · {assessment.question_count} questions
                  {assessment.deadline &&
                    ` · Due ${new Date(assessment.deadline).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {(assessment.status === "ACTIVE" ||
                  assessment.status === "CLOSED") && (
                  <Link
                    to={`/teacher/assessments/${assessment.id}/results`}
                    className="flex items-center gap-1.5 text-xs font-medium text-brand-muted hover:text-brand-ink transition-colors"
                  >
                    <BarChart2 className="w-3.5 h-3.5" aria-hidden="true" />
                    Results
                  </Link>
                )}
                <Link
                  to={`/teacher/classes/${assessment.classId}`}
                  className="text-xs font-medium text-brand-gold hover:text-brand-gold-dark"
                >
                  View class →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
