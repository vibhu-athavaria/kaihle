import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, Check, PlayCircle, Eye } from "lucide-react";
import { OnboardingLayout } from "@kaihle/ui";
import { Card, Badge, Button, ProgressBar } from "@kaihle/ui";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";
import { apiClient } from "@kaihle/auth";

interface Tier1Assessment {
  id: string;
  subject: string;
  grade: string;
  status: "not_started" | "in_progress" | "completed";
  is_system_generated: boolean;
}

export function DiagnosticHub() {
  const navigate = useNavigate();
  const { status, refetch } = useOnboardingStatus();
  const [assessments, setAssessments] = useState<Tier1Assessment[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchAssessments = async () => {
      try {
        const response = await apiClient.get<{
          assessments: Tier1Assessment[];
        }>("/api/v1/students/me/assessments");
        const tier1 =
          response.data.assessments?.filter((a) => a.is_system_generated) ?? [];
        setAssessments(tier1);
      } catch {
        setAssessments([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAssessments();
  }, []);

  useEffect(() => {
    if (status?.diagnostics_complete) {
      const timer = setTimeout(() => {
        navigate("/student/dashboard");
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [status, navigate]);

  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, 3000);
    return () => clearInterval(interval);
  }, [refetch]);

  const completedCount = assessments.filter(
    (a) => a.status === "completed",
  ).length;
  const totalCount = assessments.length;
  const allComplete = completedCount === totalCount && totalCount > 0;

  const getStatusBadge = (assessmentStatus: string) => {
    switch (assessmentStatus) {
      case "completed":
        return (
          <Badge variant="success">
            <Check className="w-3 h-3 mr-1" aria-hidden="true" /> Completed
          </Badge>
        );
      case "in_progress":
        return (
          <Badge variant="warning" pulse>
            <Clock className="w-3 h-3 mr-1" aria-hidden="true" /> In Progress
          </Badge>
        );
      default:
        return (
          <Badge variant="neutral">
            <span
              className="w-2 h-2 rounded-full bg-brand-muted mr-1"
              aria-hidden="true"
            />{" "}
            Not Started
          </Badge>
        );
    }
  };

  const getButton = (assessment: Tier1Assessment) => {
    switch (assessment.status) {
      case "completed":
        return (
          <Button
            variant="secondary"
            size="sm"
            icon={<Eye className="w-4 h-4" />}
          >
            View Results
          </Button>
        );
      case "in_progress":
        return (
          <Button
            size="sm"
            icon={<PlayCircle className="w-4 h-4" />}
            onClick={() =>
              navigate(`/student/assessments/${assessment.id}/take`)
            }
          >
            Continue
          </Button>
        );
      default:
        return (
          <Button
            size="sm"
            icon={<PlayCircle className="w-4 h-4" />}
            onClick={() =>
              navigate(`/student/assessments/${assessment.id}/take`)
            }
          >
            Start
          </Button>
        );
    }
  };

  if (status?.diagnostics_complete || allComplete) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center p-4">
        <Card className="text-center py-12 px-8 max-w-md">
          <div className="text-6xl mb-4" role="img" aria-hidden="true">
            🎉
          </div>
          <h2 className="font-display font-bold text-2xl text-brand-ink mb-2">
            You're all set!
          </h2>
          <p className="text-brand-body">
            Redirecting you to your dashboard...
          </p>
        </Card>
      </div>
    );
  }

  return (
    <OnboardingLayout step={2} totalSteps={2} stepLabel="Diagnostics">
      <div className="space-y-6">
        <div className="text-center">
          <h1 className="font-display font-bold text-2xl text-brand-ink mb-2">
            Complete your subject diagnostics
          </h1>
          <p className="text-brand-body text-sm">
            Take a quick assessment for each subject to help us personalize your
            learning path.
          </p>
        </div>

        {totalCount > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm font-semibold text-brand-body">
              <span>Progress</span>
              <span>
                {completedCount} of {totalCount} completed
              </span>
            </div>
            <ProgressBar
              value={completedCount}
              max={totalCount}
              colorClass="bg-brand-primary"
            />
          </div>
        )}

        {isLoading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary mx-auto" />
          </div>
        ) : assessments.length === 0 ? (
          <Card className="text-center py-8">
            <p className="text-brand-body">
              No diagnostics available at this time.
            </p>
          </Card>
        ) : (
          <div className="space-y-4">
            {assessments.map((assessment) => (
              <Card
                key={assessment.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-brand-primary flex items-center justify-center">
                    <span className="text-white font-bold text-sm">
                      {assessment.subject.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <h3 className="font-semibold text-brand-ink">
                      {assessment.subject}
                    </h3>
                    <p className="text-sm text-brand-muted">
                      {assessment.grade}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                  <div className="text-xs text-brand-muted">
                    <Clock className="w-3 h-3 inline mr-1" aria-hidden="true" />
                    ~15 minutes
                  </div>
                  {getStatusBadge(assessment.status)}
                  {getButton(assessment)}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </OnboardingLayout>
  );
}
