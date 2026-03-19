import { useState } from "react";
import { Card, Button, Input } from "@kaihle/ui";
import { useExtendTrial } from "../hooks/useKaihleAdmin";

type ExtensionDays = 7 | 14 | 30;

const extensionOptions: { days: ExtensionDays; label: string }[] = [
  { days: 7, label: "7 days" },
  { days: 14, label: "14 days" },
  { days: 30, label: "30 days" },
];

export function AdminExtendTrialModal({
  schoolId,
  schoolName,
  currentTrialEnd,
  onClose,
}: {
  schoolId: string;
  schoolName: string;
  currentTrialEnd: string | null;
  onClose: () => void;
}) {
  const extendTrial = useExtendTrial();
  const [selectedDays, setSelectedDays] = useState<ExtensionDays>(14);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setError("Reason is required");
      return;
    }

    try {
      await extendTrial.mutateAsync({
        id: schoolId,
        data: { days: selectedDays, reason },
      });
      onClose();
    } catch (err) {
      setError("Failed to extend trial. Please try again.");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md bg-white border border-role-admin-border">
        <div className="p-6">
          <h2 className="text-xl font-bold text-role-admin-ink mb-2">
            Extend trial
          </h2>
          <p className="text-sm text-role-admin-subtle mb-6">
            for <span className="font-semibold">{schoolName}</span>
            {currentTrialEnd && (
              <span>
                {" "}
                — Current trial ends:{" "}
                {new Date(currentTrialEnd).toLocaleDateString()}
              </span>
            )}
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-role-admin-ink mb-3">
                Extension period
              </label>
              <div className="flex gap-2">
                {extensionOptions.map((option) => (
                  <button
                    key={option.days}
                    type="button"
                    onClick={() => setSelectedDays(option.days)}
                    className={[
                      "flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-colors",
                      selectedDays === option.days
                        ? "bg-brand-primary text-white"
                        : "bg-gray-100 text-role-admin-subtle hover:bg-gray-200",
                    ].join(" ")}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <Input
              label="Reason"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError("");
              }}
              error={error}
              placeholder="Reason for extending trial (required)"
              hint="Stored for audit purposes"
            />

            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={extendTrial.isPending}>
                Extend trial
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}
