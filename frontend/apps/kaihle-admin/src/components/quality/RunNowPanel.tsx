import { useRef, useState } from "react";
import { Button, Card, Skeleton } from "@kaihle/ui";
import {
  httpStatusOf,
  newRunIntent,
  runErrorDetail,
  useCreateEvalRun,
  type EvalRunCreateRequest,
  type EvalSettings,
} from "../../hooks/useAdminQuality";

const SELECT =
  "font-['Inter'] text-sm border border-gray-200 rounded-lg px-3 py-1.5 min-h-[44px] text-gray-700 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2";

type Outcome =
  | { kind: "created"; task: string }
  | { kind: "exists"; task: string }
  | { kind: "rejected"; message: string }
  | { kind: "unavailable" };

/** Why Run now cannot be used, or null when it can. Shown as visible text, not only a tooltip. */
function disabledReason(settings: EvalSettings | undefined): string | null {
  if (!settings) return null;
  if (settings.eval_monthly_budget_usd <= 0) {
    return "The monthly budget is 0, so no run can start. Set a budget above 0 in Evaluation budget.";
  }
  if (settings.eval_enabled_tasks.length === 0) {
    return "No task is enabled. Enable at least one task under Tasks to evaluate.";
  }
  return null;
}

export function RunNowPanel({
  settings,
}: {
  settings: EvalSettings | undefined;
}) {
  const create = useCreateEvalRun();
  const [selected, setSelected] = useState("");
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  // The seed and window are fixed once per click-intent and held until the request settles,
  // so a double click re-sends the identical (task, window, seed) and the backend dedupes it.
  const intent = useRef<EvalRunCreateRequest | null>(null);

  const enabledTasks = (settings?.eval_enabled_tasks ?? []).filter((t) =>
    settings?.available_tasks.includes(t),
  );
  const task = enabledTasks.includes(selected) ? selected : enabledTasks[0];
  const reason = disabledReason(settings);
  const disabled = !settings || reason !== null || !task;

  const start = () => {
    if (!settings || !task || create.isPending) return;
    if (!intent.current) {
      intent.current = newRunIntent(task, settings.eval_window_days);
    }
    setOutcome(null);
    create.mutate(intent.current, {
      onSuccess: ({ created }) =>
        setOutcome({ kind: created ? "created" : "exists", task }),
      onError: (err) =>
        setOutcome(
          httpStatusOf(err) === 503
            ? { kind: "unavailable" }
            : {
                kind: "rejected",
                message: runErrorDetail(
                  err,
                  "Could not start the run. Please try again.",
                ),
              },
        ),
      // A settled request ends the intent: the next click, including a retry after a 503
      // (the failed run's seed will not re-enqueue), is a new run with a new seed.
      onSettled: () => {
        intent.current = null;
      },
    });
  };

  if (!settings) {
    return (
      <section aria-label="Run evaluation">
        <Card>
          <Skeleton lines={2} />
        </Card>
      </section>
    );
  }

  return (
    <section aria-label="Run evaluation">
      <Card>
        <h2 className="font-['Inter'] text-base font-bold text-brand-ink mb-1">
          Run an evaluation
        </h2>
        <p className="font-['Inter'] text-xs text-gray-500 mb-3">
          Samples recent output for one enabled task
          {settings ? ` from the last ${settings.eval_window_days} days` : ""}.
          Runs use the monthly budget.
        </p>
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="quality-run-task"
              className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400"
            >
              Task to run
            </label>
            <select
              id="quality-run-task"
              value={task ?? ""}
              onChange={(e) => setSelected(e.target.value)}
              disabled={enabledTasks.length === 0}
              className={`${SELECT} disabled:opacity-50`}
            >
              {enabledTasks.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <Button
            onClick={start}
            disabled={disabled}
            loading={create.isPending}
            aria-describedby={reason ? "quality-run-reason" : undefined}
            className="font-['Inter']"
          >
            Run now
          </Button>
        </div>
        {reason && (
          <p
            id="quality-run-reason"
            className="font-['Inter'] text-xs text-gray-600 mt-2"
          >
            {reason}
          </p>
        )}
        {outcome?.kind === "created" && (
          <p
            role="status"
            className="font-['Inter'] text-sm text-gray-700 mt-3"
          >
            Run started for {outcome.task}. It appears in Evaluation runs below.
          </p>
        )}
        {outcome?.kind === "exists" && (
          <p
            role="status"
            className="font-['Inter'] text-sm text-gray-700 mt-3"
          >
            A run for {outcome.task} with this window already exists, so nothing
            new was started.
          </p>
        )}
        {outcome?.kind === "rejected" && (
          <p
            role="alert"
            className="font-['Inter'] text-sm text-brand-red mt-3"
          >
            {outcome.message}
          </p>
        )}
        {outcome?.kind === "unavailable" && (
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            <p role="alert" className="font-['Inter'] text-sm text-brand-red">
              The evaluation worker is unavailable, so the run did not start.
            </p>
            <Button
              variant="secondary"
              onClick={start}
              loading={create.isPending}
              className="font-['Inter']"
            >
              Retry with a new seed
            </Button>
          </div>
        )}
      </Card>
    </section>
  );
}
