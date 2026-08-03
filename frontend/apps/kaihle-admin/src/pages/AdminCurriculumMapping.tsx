import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { AdminLayout, Button, EmptyState, Modal, Skeleton } from "@kaihle/ui";
import { AlertTriangle, Check, Search, Sparkles, Split, X } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface Candidate {
  objective_id: string;
  canonical_code: string;
  learning_objective: string;
  similarity: number | null;
}

interface ReviewItem {
  id: string;
  item_type: string;
  status: string;
  source_code: string;
  source_name: string | null;
  source_learning_objective: string;
  subject_code: string | null;
  grade_level: number | null;
  question_count: number;
  candidates: Candidate[];
  llm_suggested_code: string | null;
  llm_reason: string | null;
  chosen_objective_id: string | null;
  admin_note: string | null;
  resolved_at: string | null;
}

interface ReviewListResponse {
  total: number;
  items: ReviewItem[];
}

interface ReviewCounts {
  PENDING: number;
  APPROVED: number;
  REJECTED: number;
  SPLIT: number;
}

interface ObjectiveSearchItem {
  objective_id: string;
  canonical_code: string;
  name: string;
  learning_objective: string;
}

type StatusFilter = "PENDING" | "APPROVED" | "REJECTED" | "SPLIT";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "PENDING", label: "Pending" },
  { value: "APPROVED", label: "Approved" },
  { value: "SPLIT", label: "Split" },
  { value: "REJECTED", label: "Rejected" },
];

const CARD = "bg-white border border-[#eaecf0] rounded-lg";
const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1a5c38] focus-visible:ring-offset-2";

/** Distinguishes an expired session from a genuine server failure. */
function isUnauthorized(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  return status === 401 || status === 403;
}

/**
 * Similarity is shown because it explains why the pipeline hesitated, but it is
 * deliberately quiet: a reviewer should decide from the objective text, not anchor
 * on a number produced by a model that already declined to commit.
 */
function similarityLabel(similarity: number | null): string {
  if (similarity === null) return "";
  return `${Math.round(similarity * 100)}% textual match`;
}

export function AdminCurriculumMapping() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("PENDING");
  const [activeItem, setActiveItem] = useState<ReviewItem | null>(null);
  const [selectedObjectiveId, setSelectedObjectiveId] = useState<string | null>(
    null,
  );
  const [note, setNote] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<ObjectiveSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: counts } = useQuery<ReviewCounts>({
    queryKey: ["lo-review", "counts"],
    queryFn: async () => (await apiClient.get("/api/v1/lo-review/counts")).data,
  });

  const {
    data,
    isLoading,
    isError,
    error: loadError,
    refetch,
  } = useQuery<ReviewListResponse>({
    queryKey: ["lo-review", "items", statusFilter],
    queryFn: async () =>
      (
        await apiClient.get("/api/v1/lo-review/items", {
          params: { status: statusFilter },
        })
      ).data,
  });

  const closeModal = useCallback(() => {
    setActiveItem(null);
    setSelectedObjectiveId(null);
    setNote("");
    setSearchTerm("");
    setSearchResults([]);
    setError(null);
  }, []);

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["lo-review"] });
  }, [queryClient]);

  const approve = useMutation({
    mutationFn: async () => {
      if (!activeItem || !selectedObjectiveId) return null;
      return (
        await apiClient.post(
          `/api/v1/lo-review/items/${activeItem.id}/approve`,
          {
            objective_id: selectedObjectiveId,
            admin_note: note.trim() || null,
          },
        )
      ).data;
    },
    onSuccess: () => {
      invalidate();
      closeModal();
    },
    onError: (err: { response?: { data?: { detail?: string } } }) =>
      setError(err?.response?.data?.detail ?? "Could not apply this decision."),
  });

  const reject = useMutation({
    mutationFn: async () => {
      if (!activeItem) return null;
      return (
        await apiClient.post(
          `/api/v1/lo-review/items/${activeItem.id}/reject`,
          {
            admin_note: note.trim() || null,
          },
        )
      ).data;
    },
    onSuccess: () => {
      invalidate();
      closeModal();
    },
    onError: (err: { response?: { data?: { detail?: string } } }) =>
      setError(err?.response?.data?.detail ?? "Could not apply this decision."),
  });

  const split = useMutation({
    mutationFn: async () => {
      if (!activeItem) return null;
      return (
        await apiClient.post(`/api/v1/lo-review/items/${activeItem.id}/split`)
      ).data as {
        questions_bound: number;
        objectives_used: number;
        undecided: number;
      };
    },
    onSuccess: () => {
      invalidate();
      closeModal();
    },
    onError: (err: { response?: { data?: { detail?: string } } }) =>
      setError(err?.response?.data?.detail ?? "Could not split this group."),
  });

  const runSearch = useCallback(async () => {
    if (searchTerm.trim().length < 2) return;
    setSearching(true);
    try {
      const res = await apiClient.get("/api/v1/lo-review/objectives/search", {
        params: { q: searchTerm.trim() },
      });
      setSearchResults(res.data);
    } finally {
      setSearching(false);
    }
  }, [searchTerm]);

  const items = data?.items ?? [];
  const pendingQuestions = useMemo(
    () => items.reduce((sum, i) => sum + i.question_count, 0),
    [items],
  );

  return (
    <AdminLayout
      pageTitle="Curriculum Mapping"
      pageSubtitle="Questions whose curriculum placement changed and could not be re-matched automatically. Each decision re-binds every question in its group at once."
    >
      <div className="font-['Inter']">
        <div className="flex items-center gap-2 mb-4" role="tablist">
          {STATUS_TABS.map((tab) => {
            const active = statusFilter === tab.value;
            const count = counts?.[tab.value] ?? 0;
            return (
              <button
                key={tab.value}
                role="tab"
                aria-selected={active}
                onClick={() => setStatusFilter(tab.value)}
                className={`min-h-[36px] px-3 rounded-md text-xs font-semibold border transition-colors ${FOCUS} ${
                  active
                    ? "bg-[#1a5c38] border-[#1a5c38] text-white"
                    : "bg-white border-[#eaecf0] text-[#374151] hover:bg-[#f3f4f6]"
                }`}
              >
                {tab.label}
                <span
                  className={
                    active ? "ml-1.5 opacity-80" : "ml-1.5 text-[#6b7280]"
                  }
                >
                  {count}
                </span>
              </button>
            );
          })}
          {statusFilter === "PENDING" && items.length > 0 && (
            <span className="ml-auto text-xs text-[#6b7280]">
              {pendingQuestions.toLocaleString()} questions awaiting a decision
            </span>
          )}
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className={`${CARD} p-4`}>
                <Skeleton className="h-4 w-1/3 mb-3" />
                <Skeleton className="h-3 w-2/3" />
              </div>
            ))}
          </div>
        ) : isError ? (
          /*
           * A failed load must never be dressed up as an empty queue. Falling back to
           * `data?.items ?? []` showed a green tick and "Nothing waiting for review"
           * when the request had actually 401'd — reporting success for a failure.
           */
          <div className={`${CARD} p-6 text-center`}>
            <AlertTriangle
              className="w-6 h-6 text-[#b45309] mx-auto mb-3"
              aria-hidden="true"
            />
            <h3 className="text-sm font-semibold text-[#111827] mb-1">
              Could not load the review queue
            </h3>
            <p className="text-xs text-[#6b7280] mb-4">
              {isUnauthorized(loadError)
                ? "Your session has expired. Sign in again to continue."
                : "The server did not return the queue. This does not mean the queue is empty."}
            </p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => void refetch()}
            >
              Try again
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className={CARD}>
            <EmptyState
              emoji={statusFilter === "PENDING" ? "✅" : "📭"}
              title={
                statusFilter === "PENDING"
                  ? "Nothing waiting for review"
                  : `No ${statusFilter.toLowerCase()} decisions yet`
              }
              description={
                statusFilter === "PENDING"
                  ? "Every curriculum mapping has been resolved. New items appear here after a curriculum remap."
                  : "Decisions you make will be listed here."
              }
            />
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <article key={item.id} className={`${CARD} p-4`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-sm font-semibold text-[#111827]">
                        {item.source_name ?? item.source_code}
                      </h2>
                      {item.subject_code && (
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6b7280] bg-[#f3f4f6] px-1.5 py-0.5 rounded">
                          {item.subject_code}
                          {item.grade_level
                            ? ` · Grade ${item.grade_level}`
                            : ""}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#4b5563] mt-1.5 leading-relaxed">
                      {item.source_learning_objective}
                    </p>
                  </div>

                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    {/* The blast radius of the decision, stated up front. */}
                    <span className="text-xs font-semibold text-[#1a5c38] bg-[#1a5c38]/10 px-2 py-1 rounded-full whitespace-nowrap">
                      {item.question_count} question
                      {item.question_count === 1 ? "" : "s"}
                    </span>
                    {item.status === "PENDING" && (
                      <Button
                        size="sm"
                        onClick={() => {
                          setActiveItem(item);
                          setSelectedObjectiveId(
                            item.candidates[0]?.objective_id ?? null,
                          );
                        }}
                      >
                        Review
                      </Button>
                    )}
                  </div>
                </div>

                {item.status !== "PENDING" && (
                  <p className="text-[11px] text-[#6b7280] mt-3 pt-3 border-t border-[#eaecf0]">
                    {item.status === "APPROVED" ? "Approved" : "Rejected"}
                    {item.resolved_at
                      ? ` · ${new Date(item.resolved_at).toLocaleDateString()}`
                      : ""}
                    {item.admin_note ? ` · “${item.admin_note}”` : ""}
                  </p>
                )}

                {item.candidates.length === 0 && item.status === "PENDING" && (
                  <p className="flex items-center gap-1.5 text-[11px] text-[#b45309] mt-3">
                    <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
                    No close match was found — you will need to search for an
                    objective.
                  </p>
                )}
              </article>
            ))}
          </div>
        )}

        <Modal
          open={activeItem !== null}
          onOpenChange={(open) => !open && closeModal()}
          title="Choose a learning objective"
          maxWidth="3xl"
          titleClassName="font-['Inter'] font-bold text-xl text-[#111827] mb-1 pr-8"
        >
          {activeItem && (
            <div className="font-['Inter'] space-y-4">
              <div className="bg-[#f8f9fb] border border-[#eaecf0] rounded-md p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-[#6b7280] mb-1">
                  These {activeItem.question_count} questions currently test
                </p>
                <p className="text-sm text-[#111827] leading-relaxed">
                  {activeItem.source_learning_objective}
                </p>
              </div>

              {activeItem.llm_reason && (
                <p className="flex items-start gap-1.5 text-[11px] text-[#6b7280]">
                  <Sparkles
                    className="w-3.5 h-3.5 mt-0.5 flex-shrink-0"
                    aria-hidden="true"
                  />
                  <span>Automated review: {activeItem.llm_reason}</span>
                </p>
              )}

              <fieldset>
                <legend className="text-[10px] font-semibold uppercase tracking-wide text-[#6b7280] mb-2">
                  Suggested objectives
                </legend>
                <div className="space-y-2">
                  {activeItem.candidates.map((candidate) => {
                    const selected =
                      selectedObjectiveId === candidate.objective_id;
                    return (
                      <label
                        key={candidate.objective_id}
                        className={`flex gap-3 p-3 rounded-md border cursor-pointer transition-colors ${
                          selected
                            ? "border-[#1a5c38] bg-[#1a5c38]/5"
                            : "border-[#eaecf0] hover:bg-[#fafafa]"
                        }`}
                      >
                        <input
                          type="radio"
                          name="objective"
                          className={`mt-1 accent-[#1a5c38] ${FOCUS}`}
                          checked={selected}
                          onChange={() =>
                            setSelectedObjectiveId(candidate.objective_id)
                          }
                        />
                        <span className="min-w-0">
                          <span className="block text-sm text-[#111827] leading-relaxed">
                            {candidate.learning_objective}
                          </span>
                          <span className="block text-[10px] text-[#9ca3af] mt-1">
                            {candidate.canonical_code}
                            {candidate.similarity !== null
                              ? ` · ${similarityLabel(candidate.similarity)}`
                              : ""}
                          </span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div>
                <label
                  htmlFor="objective-search"
                  className="block text-[10px] font-semibold uppercase tracking-wide text-[#6b7280] mb-2"
                >
                  Or search all objectives
                </label>
                <div className="flex gap-2">
                  <input
                    id="objective-search"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && void runSearch()}
                    placeholder="e.g. ordering decimals"
                    className={`flex-1 min-h-[36px] border border-[#eaecf0] rounded-md text-xs text-[#374151] px-3 ${FOCUS}`}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={searching}
                    onClick={() => void runSearch()}
                    icon={<Search className="w-4 h-4" aria-hidden="true" />}
                  >
                    Search
                  </Button>
                </div>
                {searchResults.length > 0 && (
                  <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
                    {searchResults.map((result) => {
                      const selected =
                        selectedObjectiveId === result.objective_id;
                      return (
                        <button
                          key={result.objective_id}
                          onClick={() =>
                            setSelectedObjectiveId(result.objective_id)
                          }
                          className={`w-full text-left p-2 rounded-md border text-xs transition-colors ${FOCUS} ${
                            selected
                              ? "border-[#1a5c38] bg-[#1a5c38]/5"
                              : "border-[#eaecf0] hover:bg-[#fafafa]"
                          }`}
                        >
                          <span className="block text-[#111827]">
                            {result.learning_objective}
                          </span>
                          <span className="block text-[10px] text-[#9ca3af] mt-0.5">
                            {result.canonical_code}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div>
                <label
                  htmlFor="admin-note"
                  className="block text-[10px] font-semibold uppercase tracking-wide text-[#6b7280] mb-2"
                >
                  Note (optional)
                </label>
                <textarea
                  id="admin-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  className={`w-full border border-[#eaecf0] rounded-md text-xs text-[#374151] px-3 py-2 ${FOCUS}`}
                />
              </div>

              {error && (
                <p role="alert" className="text-xs text-[#b91c1c]">
                  {error}
                </p>
              )}

              {activeItem.candidates.length > 1 && (
                /*
                 * An old subtopic could be broader than any single new objective —
                 * "Ratio and Proportion" covers simplifying ratios, dividing a
                 * quantity, AND the unitary method, which are now three objectives.
                 * Binding all its questions to one of them mis-targets most of them.
                 */
                <div className="bg-[#fffbeb] border border-[#fde68a] rounded-md p-3">
                  <p className="text-xs text-[#92400e] leading-relaxed mb-2">
                    If these questions do not all test the same skill, assign
                    them individually instead. Each question is judged on its
                    own; anything unclear is left unbound for you rather than
                    guessed.
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={split.isPending}
                    onClick={() => split.mutate()}
                    icon={<Split className="w-4 h-4" aria-hidden="true" />}
                  >
                    Assign each question separately
                  </Button>
                  {split.isPending && (
                    <p className="text-[11px] text-[#92400e] mt-2">
                      Reviewing {activeItem.question_count} questions — this can
                      take a minute.
                    </p>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between gap-3 pt-2 border-t border-[#eaecf0]">
                <Button
                  variant="secondary"
                  size="sm"
                  loading={reject.isPending}
                  onClick={() => reject.mutate()}
                  icon={<X className="w-4 h-4" aria-hidden="true" />}
                >
                  No suitable objective
                </Button>
                <Button
                  size="sm"
                  disabled={!selectedObjectiveId}
                  loading={approve.isPending}
                  onClick={() => approve.mutate()}
                  icon={<Check className="w-4 h-4" aria-hidden="true" />}
                >
                  Bind {activeItem.question_count} question
                  {activeItem.question_count === 1 ? "" : "s"}
                </Button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </AdminLayout>
  );
}

export default AdminCurriculumMapping;
