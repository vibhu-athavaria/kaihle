import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { OnboardingLayout } from "@kaihle/ui";
import { Card, Badge, Button } from "@kaihle/ui";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";

interface DiagnosticStatusByClass {
  class_id: string;
  class_name: string;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED";
}

export function DiagnosticHub() {
  const navigate = useNavigate();
  const { status, refetch } = useOnboardingStatus();
  const [diagnostics, setDiagnostics] = useState<DiagnosticStatusByClass[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (status) {
      setDiagnostics(status.diagnostics_by_class || []);
      setIsLoading(false);
    }
  }, [status]);

  useEffect(() => {
    // Poll for completion or refetch on focus
    const interval = setInterval(() => {
      refetch();
    }, 3000);

    return () => clearInterval(interval);
  }, [refetch]);

  useEffect(() => {
    if (
      diagnostics.length > 0 &&
      diagnostics.every((d) => d.status === "COMPLETED")
    ) {
      const timer = setTimeout(() => {
        navigate("/student/dashboard");
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [diagnostics, navigate]);

  const completedCount = diagnostics.filter(
    (d) => d.status === "COMPLETED",
  ).length;
  const totalCount = diagnostics.length;
  const allComplete = totalCount > 0 && completedCount === totalCount;

  const getStatusBadge = (diagnosticStatus: string) => {
    switch (diagnosticStatus) {
      case "COMPLETED":
        return <Badge variant="success">✓ Completed</Badge>;
      case "IN_PROGRESS":
        return <Badge variant="warning">⏳ In Progress</Badge>;
      default:
        return <Badge variant="neutral">● Not Started</Badge>;
    }
  };

  const getActionButton = (diagnostic: DiagnosticStatusByClass) => {
    switch (diagnostic.status) {
      case "COMPLETED":
        return null;
      case "IN_PROGRESS":
        return (
          <Button
            variant="primary"
            size="sm"
            onClick={() =>
              navigate(`/student/assessments/${diagnostic.class_id}/take`)
            }
          >
            Continue
          </Button>
        );
      default:
        return (
          <Button
            variant="primary"
            size="sm"
            onClick={() =>
              navigate(`/student/assessments/${diagnostic.class_id}/take`)
            }
          >
            Start
          </Button>
        );
    }
  };

  if (isLoading) {
    return (
      <OnboardingLayout step={2} totalSteps={2} stepLabel="Subject diagnostics">
        <div className="text-center py-8">Loading...</div>
      </OnboardingLayout>
    );
  }

  if (allComplete) {
    return (
      <OnboardingLayout step={2} totalSteps={2} stepLabel="Subject diagnostics">
        <div className="text-center py-16">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="font-display font-bold text-2xl text-brand-ink mb-2">
            You're all set!
          </h2>
          <p className="text-brand-body">Redirecting to your dashboard...</p>
        </div>
      </OnboardingLayout>
    );
  }

  return (
    <OnboardingLayout step={2} totalSteps={2} stepLabel="Subject diagnostics">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="font-display font-bold text-2xl text-brand-ink mb-2">
            Complete your subject diagnostics
          </h1>
          <p className="text-brand-body">
            Answer a few questions for each subject to help us understand your
            current level.
          </p>
        </div>

        <div className="mb-6">
          <p className="text-sm font-semibold text-brand-body">
            {completedCount} of {totalCount} subjects completed
          </p>
        </div>

        <div className="space-y-4">
          {diagnostics.map((diagnostic) => (
            <Card
              key={diagnostic.class_id}
              variant="interactive"
              className="flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div>
                  <p className="font-semibold text-brand-ink">
                    {diagnostic.class_name}
                  </p>
                  <p className="text-sm text-brand-muted">~15 minutes</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {getStatusBadge(diagnostic.status)}
                {getActionButton(diagnostic)}
              </div>
            </Card>
          ))}
        </div>

        {diagnostics.length === 0 && (
          <div className="text-center py-8">
            <p className="text-brand-body">No diagnostics assigned yet.</p>
            <p className="text-sm text-brand-muted mt-2">
              Contact your teacher or school admin to get started.
            </p>
          </div>
        )}
      </div>
    </OnboardingLayout>
  );
}
