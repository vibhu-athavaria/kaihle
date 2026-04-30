import { useState } from "react";
import { BookOpen, Star, Trash2, Plus, X } from "lucide-react";
import { Skeleton } from "@kaihle/ui";
import {
  useSchoolCurricula,
  useAllCurricula,
  useAddSchoolCurriculum,
  useRemoveSchoolCurriculum,
  useSetPrimarySchoolCurriculum,
  type SchoolCurriculum,
} from "../../hooks/useKaihleAdmin";

interface AddCurriculumFormProps {
  schoolId: string;
  subscribedIds: Set<string>;
  onClose: () => void;
}

function AddCurriculumForm({
  schoolId,
  subscribedIds,
  onClose,
}: AddCurriculumFormProps) {
  const { data: allCurricula, isLoading } = useAllCurricula();
  const addMutation = useAddSchoolCurriculum(schoolId);
  const [selectedId, setSelectedId] = useState("");
  const [isPrimary, setIsPrimary] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const available = (allCurricula ?? []).filter(
    (c) => c.is_active && !subscribedIds.has(c.id),
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) return;
    setError(null);
    try {
      await addMutation.mutateAsync({
        curriculum_id: selectedId,
        is_primary: isPrimary,
      });
      onClose();
    } catch {
      setError("Failed to add curriculum. Please try again.");
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-4 border border-role-admin-border rounded-lg p-4 bg-[#f8f9fb]"
    >
      <div className="flex items-center justify-between mb-3">
        <p className="font-['Inter'] text-sm font-bold text-role-admin-ink">
          Add curriculum
        </p>
        <button
          type="button"
          onClick={onClose}
          className="text-role-admin-muted hover:text-role-admin-ink focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
          aria-label="Cancel"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      {isLoading ? (
        <Skeleton className="h-9 w-full" />
      ) : available.length === 0 ? (
        <p className="font-['Inter'] text-sm text-role-admin-muted py-2">
          All available curricula are already subscribed.
        </p>
      ) : (
        <>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="curriculum-select"
                className="block font-['Inter'] text-xs font-bold text-role-admin-muted mb-1"
              >
                Curriculum
              </label>
              <select
                id="curriculum-select"
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="w-full border border-role-admin-border rounded-lg px-3 py-2 font-['Inter'] text-sm text-role-admin-ink bg-white focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              >
                <option value="">Select a curriculum…</option>
                {available.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isPrimary}
                onChange={(e) => setIsPrimary(e.target.checked)}
                className="w-4 h-4 rounded accent-brand-primary"
              />
              <span className="font-['Inter'] text-sm text-role-admin-ink">
                Set as primary curriculum
              </span>
            </label>
          </div>

          {error && (
            <p className="font-['Inter'] text-xs text-red-600 mt-2">{error}</p>
          )}

          <div className="flex gap-2 mt-3">
            <button
              type="submit"
              disabled={!selectedId || addMutation.isPending}
              className="bg-brand-primary text-white rounded-full px-4 py-2 font-['Inter'] text-sm font-medium min-h-[44px] disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              {addMutation.isPending ? "Adding…" : "Add"}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={addMutation.isPending}
              className="bg-gray-100 text-role-admin-ink rounded-full px-4 py-2 font-['Inter'] text-sm font-medium min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </form>
  );
}

interface CurriculumRowProps {
  sc: SchoolCurriculum;
  schoolId: string;
}

function CurriculumRow({ sc, schoolId }: CurriculumRowProps) {
  const setPrimary = useSetPrimarySchoolCurriculum(schoolId);
  const remove = useRemoveSchoolCurriculum(schoolId);
  const [confirming, setConfirming] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const handleRemove = async () => {
    setRemoveError(null);
    try {
      await remove.mutateAsync(sc.curriculum_id);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response
        ?.status;
      if (status === 409) {
        setRemoveError("Cannot remove: this curriculum has active classes.");
      } else {
        setRemoveError("Failed to remove curriculum.");
      }
      setConfirming(false);
    }
  };

  return (
    <div className="flex items-start justify-between py-3 border-b border-role-admin-border last:border-0">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-full bg-brand-light flex items-center justify-center flex-shrink-0 mt-0.5">
          <BookOpen className="w-4 h-4 text-brand-primary" aria-hidden="true" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <p className="font-['Inter'] text-sm font-semibold text-role-admin-ink">
              {sc.curriculum_name}
            </p>
            {sc.is_primary && (
              <span className="inline-flex items-center gap-1 bg-brand-light text-brand-primary text-xs font-bold rounded-full px-2 py-0.5">
                <Star className="w-3 h-3" aria-hidden="true" />
                Primary
              </span>
            )}
          </div>
          <p className="font-['Inter'] text-xs text-role-admin-muted">
            {sc.curriculum_code}
            {sc.curriculum_description ? ` · ${sc.curriculum_description}` : ""}
          </p>
          {removeError && (
            <p className="font-['Inter'] text-xs text-red-600 mt-1">
              {removeError}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {!sc.is_primary && (
          <button
            type="button"
            onClick={() => setPrimary.mutate(sc.curriculum_id)}
            disabled={setPrimary.isPending}
            title="Set as primary"
            className="text-role-admin-subtle hover:text-brand-primary font-['Inter'] text-xs underline min-h-[44px] px-1 focus-visible:ring-2 focus-visible:ring-brand-primary rounded disabled:opacity-60"
          >
            Set primary
          </button>
        )}

        {confirming ? (
          <div className="flex items-center gap-1">
            <span className="font-['Inter'] text-xs text-red-600">Remove?</span>
            <button
              type="button"
              onClick={handleRemove}
              disabled={remove.isPending}
              className="font-['Inter'] text-xs font-bold text-red-600 hover:text-red-800 min-h-[44px] px-1 focus-visible:ring-2 focus-visible:ring-red-500 rounded"
            >
              {remove.isPending ? "…" : "Yes"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="font-['Inter'] text-xs text-role-admin-muted hover:text-role-admin-ink min-h-[44px] px-1 focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
            >
              No
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            aria-label={`Remove ${sc.curriculum_name}`}
            className="text-role-admin-muted hover:text-red-600 min-h-[44px] w-8 flex items-center justify-center focus-visible:ring-2 focus-visible:ring-red-500 rounded"
          >
            <Trash2 className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}

interface SchoolCurriculumPanelProps {
  schoolId: string;
}

export function SchoolCurriculumPanel({
  schoolId,
}: SchoolCurriculumPanelProps) {
  const { data: curricula, isLoading } = useSchoolCurricula(schoolId);
  const [showAddForm, setShowAddForm] = useState(false);

  const subscribedIds = new Set(
    (curricula ?? []).map((sc) => sc.curriculum_id),
  );

  return (
    <div className="bg-white border border-role-admin-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-['Inter'] text-sm font-bold text-role-admin-ink">
          Curricula
        </h3>
        {!showAddForm && (
          <button
            type="button"
            onClick={() => setShowAddForm(true)}
            className="inline-flex items-center gap-1 bg-brand-primary text-white rounded-full px-3 py-1.5 font-['Inter'] text-xs font-bold min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            <Plus className="w-3 h-3" aria-hidden="true" />
            Add curriculum
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : curricula && curricula.length > 0 ? (
        <div>
          {curricula.map((sc) => (
            <CurriculumRow key={sc.curriculum_id} sc={sc} schoolId={schoolId} />
          ))}
        </div>
      ) : (
        <div className="text-center py-8">
          <BookOpen
            className="w-8 h-8 text-role-admin-muted mx-auto mb-2"
            aria-hidden="true"
          />
          <p className="font-['Inter'] text-sm text-role-admin-muted">
            No curricula subscribed yet.
          </p>
          <p className="font-['Inter'] text-xs text-role-admin-muted mt-1">
            Add a curriculum to enable class creation for this school.
          </p>
        </div>
      )}

      {showAddForm && (
        <AddCurriculumForm
          schoolId={schoolId}
          subscribedIds={subscribedIds}
          onClose={() => setShowAddForm(false)}
        />
      )}
    </div>
  );
}
