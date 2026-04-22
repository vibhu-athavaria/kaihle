import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolAnalytics, useSchoolClasses } from "../hooks/useSchoolAdmin";

export function SchoolOverview() {
  const navigate = useNavigate();
  const { data: analytics, isLoading } = useSchoolAnalytics();
  const { data: classes = [] } = useSchoolClasses();

  const needsAttention = classes.filter(
    (c) => c.diagnostic_status !== "has_data",
  );
  const onboardingPct = analytics
    ? Math.round(
        (analytics.onboarding_funnel.diagnostic_done /
          Math.max(analytics.total_students, 1)) *
          100,
      )
    : 0;

  const kpis = analytics
    ? [
        { label: "Total students", value: analytics.total_students },
        { label: "Active this month", value: analytics.active_students },
        {
          label: "Assessments completed",
          value: analytics.assessments_completed,
        },
        { label: "Onboarding rate", value: `${onboardingPct}%` },
      ]
    : [];

  return (
    <DashboardLayout variant="school-admin" pageTitle="Overview">
      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-role-school-border rounded-xl" />
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4 mb-5">
            {kpis.map(({ label, value }) => (
              <div
                key={label}
                className="bg-white border border-role-school-border rounded-xl p-4"
              >
                <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-1.5">
                  {label}
                </div>
                <div className="font-display font-bold text-[26px] text-brand-ink leading-none">
                  {value}
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Students needing attention
              </div>
              {!analytics?.at_risk_students.length ? (
                <p className="text-sm text-brand-muted py-4 text-center">
                  No students at risk — great work!
                </p>
              ) : (
                <div className="space-y-2">
                  {analytics.at_risk_students.slice(0, 6).map((s) => {
                    const { label } = getMasteryStyle(s.worst_mastery);
                    const initial = s.last_name.charAt(0).toUpperCase();
                    return (
                      <div
                        key={s.student_id}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-brand-red flex items-center justify-center text-white text-[10px] font-black flex-shrink-0">
                            {s.first_name.charAt(0)}
                            {initial}
                          </div>
                          <span className="text-xs font-semibold text-brand-ink">
                            {s.first_name} {initial}.
                          </span>
                        </div>
                        <span className="text-xs text-brand-red font-bold">
                          {label} · {s.needs_work_class_count}{" "}
                          {s.needs_work_class_count === 1 ? "class" : "classes"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Classes needing setup
              </div>
              {needsAttention.length === 0 ? (
                <p className="text-sm text-brand-muted py-4 text-center">
                  All classes are set up.
                </p>
              ) : (
                <div className="space-y-2">
                  {needsAttention.slice(0, 6).map((c) => (
                    <div
                      key={c.id}
                      onClick={() =>
                        navigate(`/school-admin/classes/${c.id}/gap-map`)
                      }
                      className="flex items-center justify-between cursor-pointer hover:bg-gray-50 rounded-lg px-2 py-1 -mx-2 transition-colors"
                    >
                      <span className="text-xs font-semibold text-brand-ink">
                        {c.name}
                      </span>
                      <span
                        className={`text-[10px] font-bold ${
                          c.diagnostic_status === "setup_needed"
                            ? "text-brand-amber"
                            : "text-brand-muted"
                        }`}
                      >
                        {c.diagnostic_status === "setup_needed"
                          ? "No teacher"
                          : "Diagnostic pending"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
