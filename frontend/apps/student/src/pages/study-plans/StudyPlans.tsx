import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";

interface StudyPlan {
  id: string;
  title: string;
  status: "ACTIVE" | "IN_PROGRESS" | "COMPLETED";
  subjectName?: string;
}

interface StudyPlansResponse {
  data: StudyPlan[];
}

function useStudyPlans() {
  return useQuery<StudyPlan[]>({
    queryKey: ["student", "study-plans", "all"],
    queryFn: async () => {
      const res = await apiClient.get<StudyPlansResponse>(
        "/api/v1/students/me/study-plans?limit=50",
      );
      return res.data.data;
    },
  });
}

export function StudyPlans() {
  const { logout } = useAuth();
  const { data: studentInfo } = useStudentInfo();
  const { data: classesData } = useMyClasses();
  const { data: studyPlans, isPending } = useStudyPlans();

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  const statusLabel: Record<StudyPlan["status"], string> = {
    ACTIVE: "Ready to start",
    IN_PROGRESS: "In progress",
    COMPLETED: "Completed",
  };

  const statusColor: Record<StudyPlan["status"], string> = {
    ACTIVE: "bg-brand-light text-brand-primary",
    IN_PROGRESS: "bg-brand-amber-light text-brand-gold-dark",
    COMPLETED: "bg-brand-green-light text-brand-green",
  };

  return (
    <StudentLayout
      activeNav="study-plans"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      <div className="space-y-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Study Plans
        </h1>

        {isPending ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-16 bg-brand-border/50 rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : !studyPlans || studyPlans.length === 0 ? (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <div className="text-4xl mb-4">📚</div>
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No study plans yet
            </h3>
            <p className="font-sans text-sm text-brand-body max-w-sm mx-auto">
              Your teacher will assign study plans based on your diagnostic
              results. Check back after completing your class assessments.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {studyPlans.map((plan) => (
              <div
                key={plan.id}
                className="bg-white rounded-xl border border-brand-border p-4 flex items-center justify-between"
              >
                <div>
                  <div className="font-sans font-semibold text-sm text-brand-ink">
                    {plan.title}
                  </div>
                  {plan.subjectName && (
                    <div className="font-sans text-xs text-brand-body mt-0.5">
                      {plan.subjectName}
                    </div>
                  )}
                </div>
                <span
                  className={`font-sans text-xs font-semibold px-2.5 py-1 rounded-full ${statusColor[plan.status]}`}
                >
                  {statusLabel[plan.status]}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </StudentLayout>
  );
}
