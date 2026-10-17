import { useState } from "react";
import { Button, Card, Skeleton } from "@kaihle/ui";
import {
  buildSettingsUpdate,
  settingsErrorMessage,
  useQualityBudget,
  useSaveEvalSettings,
  type EvalSettings,
} from "../../hooks/useAdminQuality";
import { formatCost } from "../../utils/formatCost";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400 mb-1">
        {label}
      </p>
      <p className="font-['Inter'] text-xl font-bold text-brand-ink">{value}</p>
    </div>
  );
}

function BudgetEditor({ settings }: { settings: EvalSettings }) {
  const [value, setValue] = useState(String(settings.eval_monthly_budget_usd));
  const [error, setError] = useState<string | null>(null);
  const save = useSaveEvalSettings();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = Number(value);
    if (value.trim() === "" || !Number.isFinite(amount)) {
      setError("Enter a valid amount in USD.");
      return;
    }
    if (amount < 0) {
      setError("Budget cannot be negative.");
      return;
    }
    setError(null);
    save.mutate(
      buildSettingsUpdate(settings, { eval_monthly_budget_usd: amount }),
      { onError: (err) => setError(settingsErrorMessage(err)) },
    );
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-5">
      <label
        htmlFor="quality-budget-input"
        className="block font-['Inter'] text-sm font-semibold text-brand-ink mb-1.5"
      >
        Monthly budget (USD)
      </label>
      <div className="flex items-start gap-3 flex-wrap">
        <input
          id="quality-budget-input"
          type="number"
          inputMode="decimal"
          step="0.01"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={
            error ? "quality-budget-error" : "quality-budget-hint"
          }
          className={`font-['Inter'] text-sm border rounded-xl px-4 py-2.5 min-h-[44px] w-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
            error ? "border-brand-red" : "border-brand-border"
          }`}
        />
        <Button
          type="submit"
          loading={save.isPending}
          className="font-['Inter']"
        >
          Save budget
        </Button>
      </div>
      {error ? (
        <p
          id="quality-budget-error"
          role="alert"
          className="font-['Inter'] text-xs text-brand-red mt-1.5"
        >
          {error}
        </p>
      ) : (
        <p
          id="quality-budget-hint"
          className="font-['Inter'] text-xs text-brand-muted mt-1.5"
        >
          0 disables production evaluation. No run starts until this is above 0.
        </p>
      )}
    </form>
  );
}

export function BudgetPanel({
  settings,
}: {
  settings: EvalSettings | undefined;
}) {
  const { data: budget, isLoading } = useQualityBudget();

  return (
    <section aria-label="Evaluation budget">
      <Card>
        <h2 className="font-['Inter'] text-base font-bold text-brand-ink mb-4">
          Evaluation budget
        </h2>
        {isLoading || !budget ? (
          <div className="grid grid-cols-3 gap-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <Stat
              label="Budget"
              value={formatCost(budget.monthly_budget_usd)}
            />
            <Stat
              label="Month to date"
              value={formatCost(budget.month_to_date_spend_usd)}
            />
            <Stat label="Remaining" value={formatCost(budget.remaining_usd)} />
          </div>
        )}
        <p className="font-['Inter'] text-xs text-gray-500 mt-3">
          Spend is an upper estimate: unpriced calls are counted at a worst-case
          cost.
        </p>
        {settings && (
          <BudgetEditor
            key={settings.eval_monthly_budget_usd}
            settings={settings}
          />
        )}
      </Card>
    </section>
  );
}
