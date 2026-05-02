import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { ArrowRight } from "lucide-react";
import { useSchoolAnalytics, useSchoolClasses } from "../hooks/useSchoolAdmin";

const SUBJECT_BADGE: Record<string, string> = {
  math: "bg-brand-primary text-white",
  mathematics: "bg-brand-primary text-white",
  science: "bg-violet-600 text-white",
  biology: "bg-green-600 text-white",
  chemistry: "bg-amber-600 text-white",
  physics: "bg-blue-600 text-white",
  "english literature": "bg-purple-600 text-white",
  english: "bg-red-600 text-white",
};

function subjectBadgeClass(subject: string): string {
  const s = subject.toLowerCase();
  for (const [key, cls] of Object.entries(SUBJECT_BADGE)) {
    if (s.includes(key)) return cls;
  }
  return "bg-gray-500 text-white";
}

function subjectShortLabel(subject: string): string {
  const s = subject.toLowerCase();
  if (s.includes("mathematics") || s.includes("math")) return "Math";
  if (s.includes("integrated science") || s.includes("science"))
    return "Science";
  if (s.includes("english literature")) return "Eng Lit";
  if (s.includes("english")) return "English";
  if (s.includes("biology")) return "Biology";
  if (s.includes("chemistry")) return "Chemistry";
  if (s.includes("physics")) return "Physics";
  return subject;
}

export function SchoolOverview() {
  const navigate = useNavigate();
  const { data: analytics, isLoading, isError } = useSchoolAnalytics();
  const { data: classes = [] } = useSchoolClasses();

  const unassignedCount = classes.filter((c) => !c.has_teacher).length;
  const totalClasses = classes.length;

  const onboardingPct = analytics
    ? Math.round(
        (analytics.onboarding_funnel.diagnostic_done /
          Math.max(analytics.total_students, 1)) *
          100,
      )
    : 0;
  const pendingOnboarding = analytics
    ? analytics.total_students - analytics.onboarding_funnel.diagnostic_done
    : 0;

  const classesNeedingAttention = classes
    .filter((c) => c.avg_mastery !== null && c.students_below_threshold > 0)
    .sort((a, b) => (a.avg_mastery ?? 1) - (b.avg_mastery ?? 1));

  if (isLoading)
    return (
      <DashboardLayout variant="school-admin" pageTitle="Overview">
        <div className="animate-pulse space-y-5">
          <div className="grid grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 bg-role-school-border rounded-xl" />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-5">
            <div className="h-64 bg-role-school-border rounded-xl" />
            <div className="h-64 bg-role-school-border rounded-xl" />
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-role-school-border rounded-xl" />
            ))}
          </div>
        </div>
      </DashboardLayout>
    );

  if (isError)
    return (
      <DashboardLayout variant="school-admin" pageTitle="Overview">
        <div className="flex items-center justify-center py-24 text-sm font-semibold text-brand-red font-sans">
          Failed to load data. Please refresh the page.
        </div>
      </DashboardLayout>
    );

  return (
    <DashboardLayout variant="school-admin" pageTitle="Overview">
      <div className="space-y-5">
        {/* ── KPI row ── */}
        <div className="grid grid-cols-3 gap-4">
          {/* Teachers */}
          <div className="bg-white border border-role-school-border rounded-xl p-5">
            <div className="text-xs font-black uppercase tracking-[0.7px] text-role-school-muted mb-1.5">
              Teachers
            </div>
            <div className="font-display font-bold text-3xl text-brand-ink leading-none mb-1">
              {analytics?.total_teachers ?? "—"}
            </div>
            {unassignedCount > 0 && (
              <div className="text-xs text-brand-body">
                {unassignedCount} {unassignedCount === 1 ? "class" : "classes"}{" "}
                unassigned
              </div>
            )}
          </div>

          {/* Students */}
          <div className="bg-white border border-role-school-border rounded-xl p-5">
            <div className="text-xs font-black uppercase tracking-[0.7px] text-role-school-muted mb-1.5">
              Students
            </div>
            <div className="font-display font-bold text-3xl text-brand-ink leading-none mb-1">
              {analytics?.total_students ?? "—"}
            </div>
            {totalClasses > 0 && (
              <div className="text-xs text-brand-body">
                across {totalClasses} {totalClasses === 1 ? "class" : "classes"}
              </div>
            )}
          </div>

          {/* Onboarding complete */}
          <div className="bg-white border border-role-school-border rounded-xl p-5">
            <div className="text-xs font-black uppercase tracking-[0.7px] text-role-school-muted mb-1.5">
              Onboarding complete
            </div>
            <div
              className={`font-display font-bold text-3xl leading-none mb-1 ${
                onboardingPct >= 70
                  ? "text-brand-green"
                  : onboardingPct >= 40
                    ? "text-brand-amber"
                    : "text-brand-red"
              }`}
            >
              {onboardingPct}%
            </div>
            <div className="text-xs text-brand-body mb-2">
              {pendingOnboarding} student{pendingOnboarding !== 1 ? "s" : ""}{" "}
              still pending
            </div>
            <div className="w-full bg-role-school-border rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full transition-all duration-500 ${
                  onboardingPct >= 70
                    ? "bg-brand-green"
                    : onboardingPct >= 40
                      ? "bg-brand-amber"
                      : "bg-brand-red"
                }`}
                style={{ width: `${onboardingPct}%` }}
                role="progressbar"
                aria-valuenow={onboardingPct}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
          </div>
        </div>

        {/* ── Two-panel row ── */}
        <div className="grid grid-cols-2 gap-5">
          {/* Classes needing attention */}
          <div className="bg-white border border-role-school-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-bold text-brand-ink">
                Classes needing attention
              </span>
              <button
                onClick={() => navigate("/school-admin/classes")}
                className="text-xs text-brand-primary font-semibold hover:underline flex items-center gap-0.5 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
              >
                View all classes{" "}
                <ArrowRight aria-hidden="true" className="w-3 h-3" />
              </button>
            </div>

            {classesNeedingAttention.length === 0 ? (
              <div className="text-center py-8 text-sm text-brand-muted">
                All classes are on track.
              </div>
            ) : (
              <div className="space-y-2">
                {classesNeedingAttention.slice(0, 5).map((c) => {
                  const { dotClass } = getMasteryStyle(c.avg_mastery);
                  const isAtRisk = (c.avg_mastery ?? 1) < 0.4;
                  const badgeClasses = isAtRisk
                    ? "bg-red-50 text-brand-red border border-red-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200";
                  const badgeLabel = isAtRisk
                    ? `${c.students_below_threshold} at risk`
                    : `${c.students_below_threshold} developing`;

                  return (
                    <div
                      key={c.id}
                      className="flex items-center gap-2 py-1.5 px-2 -mx-2 hover:bg-gray-50 rounded-lg transition-colors"
                    >
                      <span
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`}
                        aria-label={isAtRisk ? "Needs Work" : "Developing"}
                        role="img"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-semibold text-brand-ink">
                            {c.name}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${subjectBadgeClass(c.subject_name)}`}
                          >
                            {subjectShortLabel(c.subject_name)}
                          </span>
                          <span className="text-[10px] text-brand-muted">
                            Grade {c.grade_name} · {c.student_count} students
                          </span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${badgeClasses}`}
                          >
                            {badgeLabel}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-auto">
                        {c.teacher_name && (
                          <span className="text-[10px] text-brand-muted hidden lg:block">
                            {c.teacher_name}
                          </span>
                        )}
                        <button
                          onClick={() =>
                            navigate(
                              `/school-admin/classes/${c.id}?tab=gap-map`,
                            )
                          }
                          className="text-[10px] font-bold text-brand-primary hover:underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded whitespace-nowrap"
                        >
                          Gap map →
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Students at risk */}
          <div className="bg-white border border-role-school-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-brand-ink">
                Students at risk
              </span>
              <button
                onClick={() => navigate("/school-admin/users?tab=students")}
                className="text-xs text-brand-primary font-semibold hover:underline flex items-center gap-0.5 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
              >
                Filter in Users{" "}
                <ArrowRight aria-hidden="true" className="w-3 h-3" />
              </button>
            </div>

            {analytics?.at_risk_students.length ? (
              <>
                <div className="flex items-center gap-1.5 mb-3">
                  <span
                    className="w-2 h-2 rounded-full bg-brand-red flex-shrink-0"
                    aria-hidden="true"
                  />
                  <span className="text-[10px] text-brand-red">
                    Mastery below threshold in at least one class
                  </span>
                </div>
                <div className="space-y-2">
                  {analytics.at_risk_students.slice(0, 5).map((s) => (
                    <div
                      key={s.student_id}
                      className="flex items-center justify-between py-1"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-red-100 text-red-700 flex items-center justify-center text-[10px] font-black flex-shrink-0">
                          {s.first_name.charAt(0)}
                          {s.last_name.charAt(0)}
                        </div>
                        <span className="text-xs font-semibold text-brand-ink">
                          {s.first_name} {s.last_name}
                        </span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-bold text-brand-red">
                          Needs Work
                        </div>
                        <div className="text-[10px] text-brand-muted">
                          {s.needs_work_class_count}{" "}
                          {s.needs_work_class_count === 1
                            ? "subject"
                            : "subjects"}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                {analytics.at_risk_students.length > 5 && (
                  <button
                    onClick={() => navigate("/school-admin/users?tab=students")}
                    className="mt-3 text-xs text-brand-primary font-semibold hover:underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
                  >
                    View all {analytics.at_risk_students.length} at-risk
                    students →
                  </button>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-sm text-brand-muted">
                No students at risk — great work!
              </div>
            )}
          </div>
        </div>

        {/* ── Platform activity ── */}
        <div>
          <div className="text-xs font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
            Platform activity — this week
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white border border-role-school-border rounded-xl p-5">
              <div className="text-2xl mb-1">📋</div>
              <div className="font-display font-bold text-2xl text-brand-ink leading-none mb-0.5">
                {analytics?.assessments_completed ?? "—"}
              </div>
              <div className="text-xs text-brand-body">
                Assessments completed
              </div>
            </div>

            <div className="bg-white border border-role-school-border rounded-xl p-5">
              <div className="text-2xl mb-1">📚</div>
              <div className="font-display font-bold text-2xl text-brand-ink leading-none mb-0.5">
                {analytics?.study_plans_active ?? "—"}
              </div>
              <div className="text-xs text-brand-body">Study plans active</div>
            </div>

            <div className="bg-white border border-role-school-border rounded-xl p-5">
              <div className="text-2xl mb-1">⚠️</div>
              <div
                className={`font-display font-bold text-2xl leading-none mb-0.5 ${
                  pendingOnboarding > 0 ? "text-brand-red" : "text-brand-ink"
                }`}
              >
                {pendingOnboarding}
              </div>
              <div className="text-xs text-brand-body">Pending onboarding</div>
              {pendingOnboarding > 0 && (
                <button
                  onClick={() =>
                    navigate("/school-admin/users?tab=students&filter=pending")
                  }
                  className="mt-1 text-xs font-bold text-brand-primary hover:underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
                >
                  Send reminders →
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
