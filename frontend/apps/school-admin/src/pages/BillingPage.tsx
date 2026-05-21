import { Navigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { CreditCard, Receipt, Clock, CheckCircle } from "lucide-react";
import { useAuth } from "@kaihle/auth";
import { hasPermission, Permission } from "@kaihle/types";

export function BillingPage() {
  const { logout, user } = useAuth();

  if (!hasPermission(user?.permissions, Permission.BILLING)) {
    return <Navigate to="/school-admin/dashboard" replace />;
  }

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Billing"
      onLogout={logout}
      permissions={user?.permissions}
    >
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold font-display text-gray-900">
            Billing
          </h1>
          <p className="text-gray-600 mt-1">
            Manage your subscription and payments
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Current Plan</p>
                <p className="text-xl font-bold text-gray-900 mt-1">Premium</p>
                <p className="text-sm text-brand-green mt-1">Active</p>
              </div>
              <div className="p-3 bg-brand-green/10 rounded-full">
                <CreditCard className="w-6 h-6 text-brand-green" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Next Invoice</p>
                <p className="text-xl font-bold text-gray-900 mt-1">$299.00</p>
                <p className="text-sm text-gray-500 mt-1">Due in 15 days</p>
              </div>
              <div className="p-3 bg-brand-primary/10 rounded-full">
                <Receipt className="w-6 h-6 text-brand-primary" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Payment Method</p>
                <p className="text-xl font-bold text-gray-900 mt-1">Visa</p>
                <p className="text-sm text-gray-500 mt-1">****4242</p>
              </div>
              <div className="p-3 bg-brand-primary/10 rounded-full">
                <Clock className="w-6 h-6 text-brand-primary" />
              </div>
            </div>
          </Card>
        </div>

        <Card className="p-6">
          <h2 className="text-lg font-semibold font-display text-gray-900 mb-4">
            Recent Invoices
          </h2>
          <div className="space-y-4">
            {[
              { date: "Mar 15, 2026", amount: "$299.00", status: "Paid" },
              { date: "Feb 15, 2026", amount: "$299.00", status: "Paid" },
              { date: "Jan 15, 2026", amount: "$299.00", status: "Paid" },
            ].map((invoice, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0"
              >
                <div className="flex items-center gap-3">
                  <Receipt className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="font-medium text-gray-900">{invoice.date}</p>
                    <p className="text-sm text-gray-500">
                      Monthly subscription
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="font-medium text-gray-900">
                    {invoice.amount}
                  </span>
                  <span className="flex items-center gap-1 text-sm text-brand-green">
                    <CheckCircle className="w-4 h-4" />
                    {invoice.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold font-display text-gray-900 mb-4">
            Subscription Details
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-600">Plan</span>
              <span className="font-medium text-gray-900">
                Premium (School)
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-600">Billing Cycle</span>
              <span className="font-medium text-gray-900">Monthly</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-600">Seats Included</span>
              <span className="font-medium text-gray-900">50</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-600">Seats Used</span>
              <span className="font-medium text-gray-900">23</span>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
