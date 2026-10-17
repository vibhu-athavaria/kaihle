import { useState } from "react";
import { Button, Card, Modal, Skeleton } from "@kaihle/ui";
import {
  buildSettingsUpdate,
  settingsErrorMessage,
  useSaveEvalSettings,
  type EvalSettings,
  type EvalSettingsUpdate,
} from "../../hooks/useAdminQuality";

interface SwitchProps {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onToggle: () => void;
}

function Switch({ label, checked, disabled, onToggle }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onToggle}
      className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <span
        aria-hidden="true"
        className={`relative inline-block w-10 h-6 rounded-full transition-colors ${
          checked ? "bg-brand-primary" : "bg-gray-200"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-4" : ""
          }`}
        />
      </span>
    </button>
  );
}

export function EvalSettingsPanel({
  settings,
}: {
  settings: EvalSettings | undefined;
}) {
  const save = useSaveEvalSettings();
  const [error, setError] = useState<string | null>(null);
  const [pendingTask, setPendingTask] = useState<string | null>(null);
  const [understood, setUnderstood] = useState(false);

  if (!settings) {
    return (
      <section aria-label="Evaluation settings">
        <Card>
          <Skeleton lines={4} />
        </Card>
      </section>
    );
  }

  const persist = (
    changes: Partial<EvalSettingsUpdate>,
    onDone?: () => void,
  ) => {
    setError(null);
    save.mutate(buildSettingsUpdate(settings, changes), {
      onSuccess: onDone,
      onError: (err) => setError(settingsErrorMessage(err)),
    });
  };

  const enabled = settings.eval_enabled_tasks;

  const handleToggleTask = (task: string) => {
    if (enabled.includes(task)) {
      persist({ eval_enabled_tasks: enabled.filter((t) => t !== task) });
      return;
    }
    const needsAck =
      settings.tasks_with_student_text.includes(task) &&
      !settings.student_text_acknowledgements[task];
    if (needsAck) {
      setUnderstood(false);
      setPendingTask(task);
      return;
    }
    persist({ eval_enabled_tasks: [...enabled, task] });
  };

  const closeAck = () => {
    setPendingTask(null);
    setUnderstood(false);
  };

  const confirmAck = () => {
    if (!pendingTask) return;
    persist(
      {
        eval_enabled_tasks: [...enabled, pendingTask],
        acknowledge_student_text_tasks: [pendingTask],
      },
      closeAck,
    );
  };

  return (
    <section aria-label="Evaluation settings">
      <Card>
        <h2 className="font-['Inter'] text-base font-bold text-brand-ink mb-1">
          Tasks to evaluate
        </h2>
        <p className="font-['Inter'] text-xs text-gray-500 mb-3">
          Sample of {settings.eval_sample_size_per_task} outputs per task from
          the last {settings.eval_window_days} days. Nothing is evaluated for a
          task until it is switched on.
        </p>

        <ul className="divide-y divide-gray-100">
          {settings.available_tasks.map((task) => {
            const hasStudentText =
              settings.tasks_with_student_text.includes(task);
            return (
              <li
                key={task}
                className="flex items-center justify-between gap-3 min-h-[44px]"
              >
                <span className="font-['Inter'] text-sm text-gray-700">
                  {task}
                  {hasStudentText && (
                    <span className="ml-2 font-['Inter'] text-xs text-gray-600">
                      contains student text
                    </span>
                  )}
                </span>
                <Switch
                  label={`Enable ${task}`}
                  checked={enabled.includes(task)}
                  disabled={save.isPending}
                  onToggle={() => handleToggleTask(task)}
                />
              </li>
            );
          })}
        </ul>

        <div className="flex items-center justify-between gap-3 mt-3 pt-3 border-t border-gray-100">
          <div>
            <p className="font-['Inter'] text-sm text-gray-700">
              Include indicative rubrics
            </p>
            <p className="font-['Inter'] text-xs text-gray-500">
              Judge rubrics not yet shown to agree with human labels. Results
              are always labelled indicative.
            </p>
          </div>
          <Switch
            label="Include indicative rubrics"
            checked={settings.eval_include_indicative}
            disabled={save.isPending}
            onToggle={() =>
              persist({
                eval_include_indicative: !settings.eval_include_indicative,
              })
            }
          />
        </div>

        {error && !pendingTask && (
          <p
            role="alert"
            className="font-['Inter'] text-xs text-brand-red mt-3"
          >
            {error}
          </p>
        )}
      </Card>

      <Modal
        open={pendingTask !== null}
        onOpenChange={(open) => {
          if (!open) closeAck();
        }}
        title="Evaluate student-written text?"
        titleClassName="font-['Inter'] font-bold text-xl text-brand-ink mb-1 pr-8"
        description={`Outputs of ${pendingTask ?? "this task"} are produced from text students typed.`}
      >
        <div className="space-y-4 font-['Inter']">
          <p className="text-sm text-gray-700">
            Sampled prompts and responses are sent to the judge model after
            automatic scrubbing. Scrubbing is best-effort and can miss
            locations, relatives&apos; names and personal circumstances. Only
            the Kaihle admin can see results, and no text is stored in them.
          </p>
          <label className="flex items-start gap-3 min-h-[44px] cursor-pointer">
            <input
              type="checkbox"
              checked={understood}
              onChange={(e) => setUnderstood(e.target.checked)}
              className="mt-1 w-5 h-5 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            />
            <span className="text-sm text-gray-700">
              I understand and accept this risk. Record my name and the time.
            </span>
          </label>
          {error && (
            <p role="alert" className="text-xs text-brand-red">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={closeAck}
              className="font-['Inter']"
            >
              Cancel
            </Button>
            <Button
              onClick={confirmAck}
              disabled={!understood}
              loading={save.isPending}
              className="font-['Inter']"
            >
              Enable task
            </Button>
          </div>
        </div>
      </Modal>
    </section>
  );
}
