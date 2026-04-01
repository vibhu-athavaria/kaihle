import { Link } from "react-router-dom";
import { useState, useMemo } from "react";
import { Skeleton } from "@kaihle/ui";
import { Subscription, PlanTier } from "../../hooks/useAdminBilling";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";

interface SubscriptionsTableProps {
  subscriptions: Subscription[];
  loading: boolean;
}

type SortField = "annual_value" | "school_name" | "student_count" | "status";
type SortDirection = "asc" | "desc";

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

function getAnnualValue(subscription: Subscription): number {
  if (subscription.plan_tier === "TRIAL") return 0;
  return subscription.student_count * subscription.price_per_student_annual;
}

function getDaysUntilTrialEnd(trialEndDate: string | null): number | null {
  if (!trialEndDate) return null;
  const end = new Date(trialEndDate);
  const now = new Date();
  const diff = Math.ceil(
    (end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  return diff > 0 ? diff : 0;
}

function getPlanBadgeClasses(plan: PlanTier): string {
  switch (plan) {
    case "TRIAL":
      return "bg-yellow-50 text-yellow-700 border border-yellow-200";
    case "STARTER":
      return "bg-blue-50 text-blue-700 border border-blue-200";
    case "GROWTH":
      return "bg-green-50 text-green-700 border border-green-200";
    case "SCALE":
      return "bg-purple-50 text-purple-700 border border-purple-200";
    default:
      return "bg-gray-50 text-gray-700 border border-gray-200";
  }
}

function getRowHighlightClasses(subscription: Subscription): string {
  // Past due: red left border
  if (subscription.payment_status === "PAST_DUE") {
    return "border-l-[3px] border-red-400 bg-red-50/20";
  }

  // Trial expiring < 3 days: amber left border
  if (subscription.plan_tier === "TRIAL" && subscription.trial_end_date) {
    const daysRemaining = getDaysUntilTrialEnd(subscription.trial_end_date);
    if (daysRemaining !== null && daysRemaining <= 3 && daysRemaining > 0) {
      return "border-l-[3px] border-amber-400 bg-amber-50/20";
    }
  }

  return "";
}

interface SortHeaderProps {
  field: SortField;
  label: string;
  currentSort: SortField;
  direction: SortDirection;
  onSort: (field: SortField) => void;
}

function SortHeader({
  field,
  label,
  currentSort,
  direction,
  onSort,
}: SortHeaderProps) {
  const isActive = currentSort === field;
  return (
    <button
      onClick={() => onSort(field)}
      className="flex items-center gap-1 font-inter text-[11px] uppercase tracking-wide text-gray-400 hover:text-gray-600 transition-colors"
      aria-label={`Sort by ${label}`}
    >
      {label}
      {isActive ? (
        direction === "asc" ? (
          <ArrowUp className="w-3 h-3 text-brand-primary" />
        ) : (
          <ArrowDown className="w-3 h-3 text-brand-primary" />
        )
      ) : (
        <ArrowUpDown className="w-3 h-3 text-gray-300" />
      )}
    </button>
  );
}

export function SubscriptionsTable({
  subscriptions,
  loading,
}: SubscriptionsTableProps) {
  const [sortField, setSortField] = useState<SortField>("annual_value");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const sortedSubscriptions = useMemo(() => {
    return [...subscriptions].sort((a, b) => {
      let aValue: string | number;
      let bValue: string | number;

      switch (sortField) {
        case "annual_value":
          aValue = getAnnualValue(a);
          bValue = getAnnualValue(b);
          break;
        case "school_name":
          aValue = a.school_name.toLowerCase();
          bValue = b.school_name.toLowerCase();
          break;
        case "student_count":
          aValue = a.student_count;
          bValue = b.student_count;
          break;
        case "status":
          aValue = a.payment_status;
          bValue = b.payment_status;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortDirection === "asc" ? -1 : 1;
      if (aValue > bValue) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [subscriptions, sortField, sortDirection]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left py-3 px-4 font-inter text-[11px] uppercase tracking-wide text-gray-400">
                School
              </th>
              <th className="text-left py-3 px-4 font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Plan
              </th>
              <th className="text-left py-3 px-4 font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Students
              </th>
              <th className="text-left py-3 px-4 font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Amount
              </th>
              <th className="text-left py-3 px-4 font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Status
              </th>
              <th className="text-left py-3 px-4 font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Next Billing
              </th>
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-4 px-4">
                  <Skeleton className="h-4 w-32" />
                </td>
                <td className="py-4 px-4">
                  <Skeleton className="h-6 w-16 rounded-full" />
                </td>
                <td className="py-4 px-4">
                  <Skeleton className="h-4 w-8" />
                </td>
                <td className="py-4 px-4">
                  <Skeleton className="h-4 w-16" />
                </td>
                <td className="py-4 px-4">
                  <Skeleton className="h-4 w-12" />
                </td>
                <td className="py-4 px-4">
                  <Skeleton className="h-4 w-20" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left py-3 px-4">
              <SortHeader
                field="school_name"
                label="School"
                currentSort={sortField}
                direction={sortDirection}
                onSort={handleSort}
              />
            </th>
            <th className="text-left py-3 px-4">
              <span className="font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Plan
              </span>
            </th>
            <th className="text-left py-3 px-4">
              <SortHeader
                field="student_count"
                label="Students"
                currentSort={sortField}
                direction={sortDirection}
                onSort={handleSort}
              />
            </th>
            <th className="text-left py-3 px-4">
              <SortHeader
                field="annual_value"
                label="Annual Value"
                currentSort={sortField}
                direction={sortDirection}
                onSort={handleSort}
              />
            </th>
            <th className="text-left py-3 px-4">
              <SortHeader
                field="status"
                label="Status"
                currentSort={sortField}
                direction={sortDirection}
                onSort={handleSort}
              />
            </th>
            <th className="text-left py-3 px-4">
              <span className="font-inter text-[11px] uppercase tracking-wide text-gray-400">
                Next Billing
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedSubscriptions.map((subscription) => {
            const highlightClass = getRowHighlightClasses(subscription);
            const annualValue = getAnnualValue(subscription);

            return (
              <tr
                key={subscription.id}
                className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors duration-75 ${highlightClass}`}
              >
                <td className="py-4 px-4">
                  <Link
                    to={`/kaihle-admin/schools/${subscription.school_id}`}
                    className="font-inter text-sm font-medium text-gray-700 hover:text-brand-primary"
                  >
                    {subscription.school_name}
                  </Link>
                </td>
                <td className="py-4 px-4">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getPlanBadgeClasses(
                      subscription.plan_tier,
                    )}`}
                  >
                    {subscription.plan_tier}
                  </span>
                </td>
                <td className="py-4 px-4">
                  <span className="font-inter text-sm text-gray-700">
                    {subscription.student_count}
                  </span>
                </td>
                <td className="py-4 px-4">
                  <span
                    className={`font-inter text-sm font-medium ${
                      annualValue > 0 ? "text-brand-primary" : "text-gray-400"
                    }`}
                  >
                    {annualValue > 0 ? formatCurrency(annualValue) : "—"}
                  </span>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        subscription.payment_status === "ACTIVE"
                          ? "bg-green-500"
                          : subscription.payment_status === "PAST_DUE"
                            ? "bg-red-500"
                            : "bg-gray-300"
                      }`}
                      aria-label={subscription.payment_status}
                    />
                    <span className="font-inter text-sm text-gray-700">
                      {subscription.payment_status === "PAST_DUE"
                        ? "Past Due"
                        : subscription.payment_status}
                    </span>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <span className="font-inter text-sm text-gray-500">
                    {subscription.next_billing_date
                      ? new Date(
                          subscription.next_billing_date,
                        ).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })
                      : subscription.trial_end_date
                        ? `Trial: ${getDaysUntilTrialEnd(
                            subscription.trial_end_date,
                          )}d`
                        : "—"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {sortedSubscriptions.length === 0 && (
        <div className="py-12 text-center">
          <p className="font-inter text-sm text-gray-400">
            No subscriptions found
          </p>
        </div>
      )}
    </div>
  );
}
