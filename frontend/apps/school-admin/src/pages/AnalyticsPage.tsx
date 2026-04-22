import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolAnalytics } from "../hooks/useSchoolAdmin";

type Period = "week" | "month";

function periodDates(p: Period): { from: string; to: string } {
  const today = new Date();
  const to = today.toISOString().split("T")[0];
  const from = new Date(today);
  if (p === "week") from.setDate(from.getDate() - 7);
  else from.setMonth(from.getMonth() - 1);
  return { from: from.toISOString().split("T")[0], to };
}

function masteryColor(score: number | null) {
  if (score === null) return "#9ca3af";
  if (score > 0.7) return "#16a34a";
  if (score >= 0.4) return "#f59e0b";
  return "#ef4444";
}

export function AnalyticsPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<Period>("month");
  const { from, to } = periodDates(period);
  const { data, isLoading } = useSchoolAnalytics(from, to);

  const funnel = data?.onboarding_funnel;
  const total = funnel?.invited ?? 1;

  const funnelSteps = funnel
    ? [
        { label: "Invited", count: funnel.invited },
        { label: "Password set", count: funnel.password_set },
        { label: "Profile complete", count: funnel.profile_complete },
        { label: "Diagnostic done", count: funnel.diagnostic_done },
      ]
    : [];

  const subjectGroups = (data?.classes ?? []).reduce<Record<string, number[]>>(
    (acc, c) => {
      const subj = c.class_name.split("—")[1]?.trim() ?? c.class_name;
      if (!acc[subj]) acc[subj] = [];
      if (c.avg_mastery !== null) acc[subj].push(c.avg_mastery);
      return acc;
    },
    {},
  );

  const onboardingPct = funnel
    ? Math.round((funnel.diagnostic_done / Math.max(funnel.invited, 1)) * 100)
    : 0;

  const kpis = data
    ? [
        {
          label: "Active students",
          value: `${data.active_students}/${data.total_students}`,
        },
        { label: "Assessments completed", value: data.assessments_completed },
        { label: "Study plans active", value: data.study_plans_active },
        { label: "Onboarding rate", value: `${onboardingPct}%` },
      ]
    : [];

  return (
    <DashboardLayout variant="school-admin" pageTitle="Analytics">
      <div className="flex items-center gap-1 mb-5 bg-white border border-role-school-border rounded-lg p-1 self-start w-fit">
        {(["week", "month"] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-4 py-1.5 rounded-md text-xs font-bold transition-colors ${
              period === p
                ? "bg-brand-primary text-white"
                : "text-brand-muted hover:text-brand-ink"
            }`}
          >
            {p === "week" ? "This week" : "This month"}
          </button>
        ))}
        <button className="px-4 py-1.5 rounded-md text-xs font-bold text-brand-muted opacity-40 cursor-not-allowed">
          This term
        </button>
      </div>

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

          <div className="grid grid-cols-2 gap-5 mb-5">
            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Mastery by subject
              </div>
              <div className="space-y-3">
                {Object.entries(subjectGroups).map(([subj, scores]) => {
                  const avg = scores.length
                    ? scores.reduce((a, b) => a + b, 0) / scores.length
                    : null;
                  const color = masteryColor(avg);
                  const { label } = getMasteryStyle(avg);
                  const pct = avg !== null ? Math.round(avg * 100) : 0;
                  return (
                    <div key={subj}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-semibold text-brand-ink">
                          {subj}
                        </span>
                        <span className="text-xs font-bold" style={{ color }}>
                          {label}
                        </span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="h-2 rounded-full"
                          style={{ width: `${pct}%`, background: color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Onboarding funnel
              </div>
              <div className="space-y-3">
                {funnelSteps.map((step, i) => {
                  const next = funnelSteps[i + 1];
                  const dropoff = next ? step.count - next.count : 0;
                  const pct = Math.round(
                    (step.count / Math.max(total, 1)) * 100,
                  );
                  return (
                    <div key={step.label}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-semibold text-brand-ink">
                          {step.label}
                        </span>
                        <span className="text-xs font-bold text-brand-ink">
                          {step.count}
                        </span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="h-2 rounded-full bg-brand-primary"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      {next && dropoff > 0 && (
                        <div className="text-[10px] text-brand-red font-bold mt-0.5">
                          −{dropoff} dropped off
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[#fafcfa] border-b border-role-school-border">
                  {[
                    "Class",
                    "Mastery",
                    "At risk",
                    "Students",
                    "Assessments",
                    "",
                  ].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-[10px] text-left text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data?.classes ?? []).map((c) => {
                  const { dotClass, label } = getMasteryStyle(c.avg_mastery);
                  return (
                    <tr
                      key={c.class_id}
                      onClick={() =>
                        navigate(`/school-admin/classes/${c.class_id}/gap-map`)
                      }
                      className="border-b border-[#f0f5ee] last:border-0 cursor-pointer hover:bg-[#fafcfa] transition-colors"
                    >
                      <td className="px-4 py-3 font-bold text-[13px] text-brand-ink">
                        {c.class_name}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`w-2 h-2 rounded-full ${dotClass}`}
                          />
                          <span className="text-xs font-semibold">{label}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {c.avg_mastery !== null && c.avg_mastery < 0.4 ? (
                          <span className="text-[10px] font-bold bg-red-50 text-brand-red rounded-full px-2 py-0.5">
                            At risk
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-xs text-brand-muted">
                        {c.student_count}
                      </td>
                      <td className="px-4 py-3 text-xs text-brand-muted">
                        {c.assessments_completed}
                      </td>
                      <td className="px-4 py-3 text-brand-muted text-base">
                        ›
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
