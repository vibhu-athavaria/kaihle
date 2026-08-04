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
  /** Questions in this item that still have no objective. 0 means genuinely done. */
  unbound_count: number;
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

interface ItemQuestion {
  question_id: string;
  question_text: string;
  question_type: string;
  difficulty_level: number | null;
  objective_id: string | null;
  objective_code: string | null;
  objective_text: string | null;
}

interface ItemQuestionsResponse {
  item_id: string;
  source_name: string | null;
  source_learning_objective: string;
  total: number;
  unbound: number;
  questions: ItemQuestion[];
}

interface ObjectivePlacement {
  subject_code: string;
  grade_level: number;
  topic_name: string;
  subtopic_name: string;
}

interface ObjectiveSearchItem {
  objective_id: string;
  canonical_code: string;
  name: string;
  learning_objective: string;
  match: "literal" | "semantic";
  placements: ObjectivePlacement[];
}

type StatusFilter = "PENDING" | "APPROVED" | "REJECTED" | "SPLIT";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "PENDING", label: "Pending" },
  { value: "APPROVED", label: "Approved" },
  { value: "SPLIT", label: "Split" },
  { value: "REJECTED", label: "Rejected" },
];

const STATUS_LABEL: Record<string, string> = {
  APPROVED: "Approved",
  REJECTED: "Rejected",
  SPLIT: "Split per question",
  PENDING: "Pending",
};

const CARD = "bg-white border border-[#eaecf0] rounded-lg";
const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1a5c38] focus-visible:ring-offset-2";

interface GradeGroup {
  key: string;
  label: string;
  /** The grade the question under review belongs to — sorted first and marked. */
  isFocus: boolean;
  rows: { result: ObjectiveSearchItem; contexts: string[] }[];
}

/**
 * Objectives are grade-agnostic by design — grade is a property of placement, not of
 * the concept. A reviewer, though, is always placing a question of a known grade, so
 * grade is the axis they filter by mentally. Grouping by it does that work for them.
 *
 * An objective taught in several grades appears under each, showing that grade's own
 * subtopic. That repetition is the point: "Deriving and using formulae" exists in both
 * Grade 6 and Grade 7, and only the subtopic distinguishes them. Binding is still
 * grade-agnostic — picking either row binds the same objective.
 */
function groupByGrade(
  results: ObjectiveSearchItem[],
  focusGrade?: number | null,
): GradeGroup[] {
  const byGrade = new Map<
    number,
    Map<string, { result: ObjectiveSearchItem; contexts: Set<string> }>
  >();
  const unplaced: ObjectiveSearchItem[] = [];

  for (const r of results) {
    if (!r.placements || r.placements.length === 0) {
      unplaced.push(r);
      continue;
    }
    for (const p of r.placements) {
      let group = byGrade.get(p.grade_level);
      if (!group) {
        group = new Map();
        byGrade.set(p.grade_level, group);
      }
      const entry = group.get(r.objective_id) ?? {
        result: r,
        contexts: new Set<string>(),
      };
      entry.contexts.add(
        `${p.subject_code} · ${p.topic_name} · ${p.subtopic_name}`,
      );
      group.set(r.objective_id, entry);
    }
  }

  const groups: GradeGroup[] = [...byGrade.entries()]
    .map(([grade, entries]) => ({
      key: `grade-${grade}`,
      label: `Grade ${grade}`,
      isFocus: grade === focusGrade,
      rows: [...entries.values()].map((e) => ({
        result: e.result,
        contexts: [...e.contexts].sort(),
      })),
    }))
    .sort(
      (a, b) =>
        Number(b.isFocus) - Number(a.isFocus) ||
        Number(a.key.slice(6)) - Number(b.key.slice(6)),
    );

  // An unplaced objective is unreachable by any class and is a data defect, not a
  // valid target — it sorts last and is styled as a warning, never hidden.
  if (unplaced.length > 0) {
    groups.push({
      key: "unplaced",
      label: "Not placed in any curriculum",
      isFocus: false,
      rows: unplaced.map((r) => ({ result: r, contexts: [] })),
    });
  }
  return groups;
}

/** The search result list, shared by all three places a reviewer picks an objective. */
function ObjectiveResults({
  results,
  focusGrade,
  selectedId,
  disabled,
  onSelect,
}: {
  results: ObjectiveSearchItem[];
  focusGrade?: number | null;
  selectedId?: string | null;
  disabled?: boolean;
  onSelect: (objectiveId: string) => void;
}) {
  if (results.length === 0) return null;
  const groups = groupByGrade(results, focusGrade);

  return (
    <div className="mt-2 space-y-2">
      {groups.map((group) => (
        <div key={group.key}>
          <div className="flex items-center gap-1.5 px-0.5 pb-1">
            <span
              className={`font-['Inter'] text-[10px] font-bold uppercase tracking-wide ${
                group.key === "unplaced" ? "text-[#b45309]" : "text-[#6b7280]"
              }`}
            >
              {group.label}
            </span>
            {group.isFocus && (
              <span className="text-[9px] font-semibold text-[#1a5c38] bg-[#1a5c38]/10 px-1.5 py-0.5 rounded">
                this question&rsquo;s grade
              </span>
            )}
          </div>
          <div className="space-y-1">
            {group.rows.map(({ result, contexts }) => {
              const selected = selectedId === result.objective_id;
              return (
                <button
                  key={`${group.key}-${result.objective_id}`}
                  disabled={disabled}
                  onClick={() => onSelect(result.objective_id)}
                  className={`w-full text-left p-2 rounded-md border text-xs transition-colors disabled:opacity-50 ${FOCUS} ${
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
                    {result.match === "semantic" ? " · matched by meaning" : ""}
                  </span>
                  {contexts.length === 0 ? (
                    <span className="block text-[10px] text-[#b45309] mt-1">
                      No curriculum placement
                    </span>
                  ) : (
                    <span className="flex flex-wrap gap-1 mt-1">
                      {contexts.map((c) => (
                        <span
                          key={c}
                          className="text-[10px] text-[#374151] bg-[#f3f4f6] px-1.5 py-0.5 rounded"
                        >
                          {c}
                        </span>
                      ))}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

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
  const [inspecting, setInspecting] = useState<ReviewItem | null>(null);
  const [rebindTarget, setRebindTarget] = useState<ItemQuestion | null>(null);
  const [selectedQuestions, setSelectedQuestions] = useState<Set<string>>(
    new Set(),
  );

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

  const { data: itemQuestions, isLoading: questionsLoading } =
    useQuery<ItemQuestionsResponse>({
      queryKey: ["lo-review", "questions", inspecting?.id],
      enabled: inspecting !== null,
      queryFn: async () =>
        (
          await apiClient.get(
            `/api/v1/lo-review/items/${inspecting?.id}/questions`,
          )
        ).data,
    });

  const rebind = useMutation({
    mutationFn: async (vars: {
      questionIds: string[];
      objectiveId: string | null;
    }) =>
      (
        await apiClient.patch("/api/v1/lo-review/questions/objective", {
          question_ids: vars.questionIds,
          objective_id: vars.objectiveId,
        })
      ).data,
    onSuccess: () => {
      // Invalidate the whole namespace: a rebind changes the item's unassigned
      // count as well as the question list.
      void queryClient.invalidateQueries({ queryKey: ["lo-review"] });
      setRebindTarget(null);
      setSelectedQuestions(new Set());
      setSearchResults([]);
      setSearchTerm("");
    },
  });

  const toggleQuestion = useCallback((id: string) => {
    setSelectedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

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
                      {/* A remainder item has no candidate objectives by construction,
                          so it can never be group-approved — every question is assigned
                          one at a time. Once that work is done the badge must stop
                          demanding it, or it contradicts the "All assigned" state. */}
                      {item.item_type === "QUESTION_REMAP_REMAINDER" &&
                        (item.unbound_count > 0 ? (
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-[#92400e] bg-[#fffbeb] border border-[#fde68a] px-1.5 py-0.5 rounded">
                            Needs individual review
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6b7280] bg-[#f3f4f6] px-1.5 py-0.5 rounded">
                            Assigned individually
                          </span>
                        ))}
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
                    {/* A split is not finished just because it ran — the adjudicator
                        declines on ambiguous questions. State what is left so a
                        reviewer need not open every card to find out. */}
                    {item.unbound_count > 0 ? (
                      <span className="text-[10px] font-semibold text-[#b45309] bg-[#b45309]/10 px-2 py-0.5 rounded-full whitespace-nowrap">
                        {item.unbound_count} still unassigned
                      </span>
                    ) : (
                      <span className="text-[10px] font-semibold text-[#1a5c38] px-2 py-0.5 whitespace-nowrap">
                        All assigned
                      </span>
                    )}
                    {item.status === "PENDING" &&
                    item.item_type !== "QUESTION_REMAP_REMAINDER" ? (
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
                    ) : (
                      <Button
                        size="sm"
                        variant={
                          item.status === "PENDING" ? "primary" : "secondary"
                        }
                        onClick={() => setInspecting(item)}
                      >
                        {item.status === "PENDING"
                          ? "Assign individually"
                          : "Inspect questions"}
                      </Button>
                    )}
                  </div>
                </div>

                {item.status !== "PENDING" && (
                  <p className="text-[11px] text-[#6b7280] mt-3 pt-3 border-t border-[#eaecf0]">
                    {STATUS_LABEL[item.status] ?? item.status}
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
                <div className="max-h-64 overflow-y-auto">
                  <ObjectiveResults
                    results={searchResults}
                    focusGrade={activeItem?.grade_level}
                    selectedId={selectedObjectiveId}
                    onSelect={setSelectedObjectiveId}
                  />
                </div>
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

        <Modal
          open={inspecting !== null}
          onOpenChange={(open) => {
            if (!open) {
              setInspecting(null);
              setRebindTarget(null);
              setSearchResults([]);
              setSearchTerm("");
            }
          }}
          title="Questions in this group"
          maxWidth="3xl"
          titleClassName="font-['Inter'] font-bold text-xl text-[#111827] mb-1 pr-8"
        >
          <div className="font-['Inter'] space-y-3">
            {questionsLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : !itemQuestions ? (
              <p className="text-xs text-[#b91c1c]">
                Could not load these questions.
              </p>
            ) : (
              <>
                <p className="text-xs text-[#6b7280]">
                  {itemQuestions.total} questions ·{" "}
                  <span
                    className={
                      itemQuestions.unbound > 0 ? "text-[#b45309]" : ""
                    }
                  >
                    {itemQuestions.unbound} still unassigned
                  </span>
                </p>

                {/* Bulk assignment. Questions a split leaves behind often share an
                    objective outright — three "Calculate N x M" rows are one decision,
                    not three — so selecting them together avoids fatigue errors on the
                    least ambiguous cases. */}
                <div className="flex items-center gap-3 flex-wrap">
                  <label className="flex items-center gap-2 text-xs text-[#374151] cursor-pointer">
                    <input
                      type="checkbox"
                      className={`accent-[#1a5c38] ${FOCUS}`}
                      checked={
                        selectedQuestions.size > 0 &&
                        selectedQuestions.size ===
                          itemQuestions.questions.length
                      }
                      onChange={(e) =>
                        setSelectedQuestions(
                          e.target.checked
                            ? new Set(
                                itemQuestions.questions.map(
                                  (q) => q.question_id,
                                ),
                              )
                            : new Set(),
                        )
                      }
                    />
                    Select all
                  </label>
                  <button
                    onClick={() =>
                      setSelectedQuestions(
                        new Set(
                          itemQuestions.questions
                            .filter((q) => q.objective_id === null)
                            .map((q) => q.question_id),
                        ),
                      )
                    }
                    className={`text-xs font-semibold text-[#1a5c38] hover:underline ${FOCUS}`}
                  >
                    Select unassigned ({itemQuestions.unbound})
                  </button>
                  {selectedQuestions.size > 0 && (
                    <span className="text-xs text-[#111827] font-semibold ml-auto">
                      {selectedQuestions.size} selected
                    </span>
                  )}
                </div>

                {selectedQuestions.size > 0 && (
                  <div className="bg-[#f0f7f3] border border-[#1a5c38]/25 rounded-md p-3 space-y-2">
                    <p className="text-xs text-[#111827]">
                      Assign {selectedQuestions.size} question
                      {selectedQuestions.size === 1 ? "" : "s"} to:
                    </p>
                    <div className="flex gap-2">
                      <input
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && void runSearch()}
                        placeholder="Search objectives"
                        aria-label="Search objectives for bulk assignment"
                        className={`flex-1 min-h-[34px] border border-[#eaecf0] rounded-md text-xs px-2 bg-white ${FOCUS}`}
                      />
                      <Button
                        variant="secondary"
                        size="sm"
                        loading={searching}
                        onClick={() => void runSearch()}
                      >
                        Search
                      </Button>
                    </div>
                    <ObjectiveResults
                      results={searchResults}
                      focusGrade={inspecting?.grade_level}
                      disabled={rebind.isPending}
                      onSelect={(objectiveId) =>
                        rebind.mutate({
                          questionIds: [...selectedQuestions],
                          objectiveId,
                        })
                      }
                    />
                  </div>
                )}

                <div className="max-h-[26rem] overflow-y-auto space-y-2 pr-1">
                  {itemQuestions.questions.map((q) => (
                    <div
                      key={q.question_id}
                      className={`border rounded-md p-3 ${
                        selectedQuestions.has(q.question_id)
                          ? "border-[#1a5c38] bg-[#1a5c38]/5"
                          : "border-[#eaecf0]"
                      }`}
                    >
                      <label className="flex gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          className={`mt-1 accent-[#1a5c38] flex-shrink-0 ${FOCUS}`}
                          checked={selectedQuestions.has(q.question_id)}
                          onChange={() => toggleQuestion(q.question_id)}
                        />
                        <span className="text-sm text-[#111827] leading-relaxed">
                          {q.question_text}
                        </span>
                      </label>
                      <div className="flex items-start justify-between gap-3 mt-2">
                        {q.objective_code ? (
                          <span className="text-[11px] text-[#4b5563] leading-relaxed">
                            <Check
                              className="w-3 h-3 inline mr-1 text-[#1a5c38]"
                              aria-hidden="true"
                            />
                            {q.objective_text}
                            <span className="block text-[10px] text-[#9ca3af] mt-0.5">
                              {q.objective_code}
                            </span>
                          </span>
                        ) : (
                          /* Unassigned is a real state, not a failure — the model
                             declined rather than guessing. Say so plainly. */
                          <span className="text-[11px] text-[#b45309]">
                            <AlertTriangle
                              className="w-3 h-3 inline mr-1"
                              aria-hidden="true"
                            />
                            Not assigned — needs a decision
                          </span>
                        )}
                        <button
                          onClick={() => {
                            setRebindTarget(q);
                            setSearchTerm("");
                            setSearchResults([]);
                          }}
                          className={`text-[11px] font-semibold text-[#1a5c38] hover:underline flex-shrink-0 ${FOCUS}`}
                        >
                          {q.objective_code ? "Change" : "Assign"}
                        </button>
                      </div>

                      {rebindTarget?.question_id === q.question_id && (
                        <div className="mt-3 pt-3 border-t border-[#eaecf0] space-y-2">
                          <div className="flex gap-2">
                            <input
                              value={searchTerm}
                              onChange={(e) => setSearchTerm(e.target.value)}
                              onKeyDown={(e) =>
                                e.key === "Enter" && void runSearch()
                              }
                              placeholder="Search objectives"
                              aria-label="Search objectives"
                              className={`flex-1 min-h-[32px] border border-[#eaecf0] rounded-md text-xs px-2 ${FOCUS}`}
                            />
                            <Button
                              variant="secondary"
                              size="sm"
                              loading={searching}
                              onClick={() => void runSearch()}
                            >
                              Search
                            </Button>
                          </div>
                          <ObjectiveResults
                            results={searchResults}
                            focusGrade={inspecting?.grade_level}
                            disabled={rebind.isPending}
                            onSelect={(objectiveId) =>
                              rebind.mutate({
                                questionIds: [q.question_id],
                                objectiveId,
                              })
                            }
                          />
                          {q.objective_code && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() =>
                                rebind.mutate({
                                  questionIds: [q.question_id],
                                  objectiveId: null,
                                })
                              }
                            >
                              Unassign this question
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </Modal>
      </div>
    </AdminLayout>
  );
}

export default AdminCurriculumMapping;
