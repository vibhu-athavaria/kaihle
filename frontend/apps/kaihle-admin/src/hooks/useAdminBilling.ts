import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type PlanTier = "TRIAL" | "STARTER" | "GROWTH" | "SCALE";
export type PaymentStatus = "ACTIVE" | "PAST_DUE" | "SUSPENDED";

export interface Subscription {
  id: string;
  school_id: string;
  school_name: string;
  plan_tier: PlanTier;
  payment_status: PaymentStatus;
  student_count: number;
  price_per_student_annual: number;
  trial_end_date: string | null;
  next_billing_date: string | null;
}

export interface BillingSummary {
  total_revenue: number;
  active_schools: number;
  mrr: number;
  arr: number;
  past_due_count: number;
  trials_expiring_count: number;
}

export interface BillingResponse {
  subscriptions: Subscription[];
  summary: BillingSummary;
}

function calculateBillingSummary(
  subscriptions: Subscription[],
): BillingSummary {
  const pastDueCount = subscriptions.filter(
    (s) => s.payment_status === "PAST_DUE",
  ).length;

  const now = new Date();
  const threeDaysFromNow = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);

  const trialsExpiringCount = subscriptions.filter((s) => {
    if (s.plan_tier !== "TRIAL" || !s.trial_end_date) return false;
    const trialEnd = new Date(s.trial_end_date);
    return trialEnd <= threeDaysFromNow && trialEnd > now;
  }).length;

  const activePaidSubscriptions = subscriptions.filter(
    (s) => s.plan_tier !== "TRIAL" && s.payment_status === "ACTIVE",
  );

  const mrr = activePaidSubscriptions.reduce(
    (sum, s) => sum + (s.student_count * s.price_per_student_annual) / 12,
    0,
  );

  return {
    total_revenue: mrr * 12,
    active_schools: activePaidSubscriptions.length,
    mrr,
    arr: mrr * 12,
    past_due_count: pastDueCount,
    trials_expiring_count: trialsExpiringCount,
  };
}

export function useAdminBilling() {
  return useQuery({
    queryKey: ["admin", "billing"],
    queryFn: async () => {
      // Mock data for billing UI (no backend integration - UI stub)
      const mockSubscriptions: Subscription[] = [
        {
          id: "1",
          school_id: "school-1",
          school_name: "Greenwood Academy",
          plan_tier: "SCALE",
          payment_status: "ACTIVE",
          student_count: 250,
          price_per_student_annual: 120,
          trial_end_date: null,
          next_billing_date: "2026-04-15",
        },
        {
          id: "2",
          school_id: "school-2",
          school_name: "Riverside School",
          plan_tier: "GROWTH",
          payment_status: "ACTIVE",
          student_count: 120,
          price_per_student_annual: 96,
          trial_end_date: null,
          next_billing_date: "2026-04-20",
        },
        {
          id: "3",
          school_id: "school-3",
          school_name: "Sunrise International",
          plan_tier: "STARTER",
          payment_status: "PAST_DUE",
          student_count: 45,
          price_per_student_annual: 72,
          trial_end_date: null,
          next_billing_date: "2026-03-10",
        },
        {
          id: "4",
          school_id: "school-4",
          school_name: "Oak Valley Prep",
          plan_tier: "TRIAL",
          payment_status: "ACTIVE",
          student_count: 30,
          price_per_student_annual: 0,
          trial_end_date: "2026-03-27",
          next_billing_date: null,
        },
        {
          id: "5",
          school_id: "school-5",
          school_name: "Lakewood Elementary",
          plan_tier: "TRIAL",
          payment_status: "ACTIVE",
          student_count: 80,
          price_per_student_annual: 0,
          trial_end_date: "2026-04-10",
          next_billing_date: null,
        },
        {
          id: "6",
          school_id: "school-6",
          school_name: "Mountain View High",
          plan_tier: "GROWTH",
          payment_status: "ACTIVE",
          student_count: 180,
          price_per_student_annual: 96,
          trial_end_date: null,
          next_billing_date: "2026-04-25",
        },
        {
          id: "7",
          school_id: "school-7",
          school_name: "Harbor School",
          plan_tier: "STARTER",
          payment_status: "ACTIVE",
          student_count: 55,
          price_per_student_annual: 72,
          trial_end_date: null,
          next_billing_date: "2026-04-05",
        },
        {
          id: "8",
          school_id: "school-8",
          school_name: "Pinecrest Academy",
          plan_tier: "TRIAL",
          payment_status: "ACTIVE",
          student_count: 25,
          price_per_student_annual: 0,
          trial_end_date: "2026-03-26",
          next_billing_date: null,
        },
      ];

      const summary = calculateBillingSummary(mockSubscriptions);

      return {
        subscriptions: mockSubscriptions,
        summary,
      } as BillingResponse;
    },
  });
}
