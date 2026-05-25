import { useState } from "react";
import {
  AlertCircle,
  ArrowUpCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Pencil,
} from "lucide-react";
import { AdminLayout, Modal } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  usePromotionQueue,
  usePromoteContent,
  useEditContentRow,
  type PromotionQueueItem,
} from "../../hooks/useSubtopicContent";

const PAGE_SIZE = 15;

function ContentTypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    video: "bg-blue-50 text-blue-700 border border-blue-200",
    explanation: "bg-purple-50 text-purple-700 border border-purple-200",
    quiz: "bg-amber-50 text-amber-700 border border-amber-200",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${map[type] ?? "bg-gray-100 text-gray-600"}`}
    >
      {type}
    </span>
  );
}

// ── Interest category label map ───────────────────────────────────────────────

const INTEREST_LABELS: Record<string, string> = {
  sports_movement: "Sports & Fitness",
  tech_gaming: "Technology & Innovation",
  nature_animals: "Nature & Science",
  arts_culture: "Music & Arts",
};

// ── Quiz questions preview ─────────────────────────────────────────────────

function QuizPreview({ questions }: { questions: Record<string, unknown>[] }) {
  return (
    <ol className="space-y-4">
      {questions.map((q, i) => {
        // Safely extract options — guard against API shape drift without silent failures
        const rawOptions = Array.isArray(q.options) ? q.options : [];
        const options = rawOptions.filter(
          (o): o is { key: string; text: string } =>
            typeof o === "object" && o !== null && "key" in o && "text" in o,
        );
        const questionId =
          typeof q.question_id === "string" ? q.question_id : String(i);
        return (
          <li key={questionId} className="space-y-1">
            <p className="font-['Inter'] text-xs font-semibold text-role-admin-ink">
              {i + 1}. {String(q.question_text ?? "")}
            </p>
            {options.length > 0 && (
              <ul className="pl-4 space-y-0.5">
                {options.map((opt) => (
                  <li
                    key={opt.key}
                    className={`font-['Inter'] text-xs ${
                      opt.key === q.correct_answer
                        ? "text-brand-primary font-semibold"
                        : "text-role-admin-subtle"
                    }`}
                  >
                    {opt.key}. {opt.text}
                    {opt.key === q.correct_answer && " ✓"}
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ── Review modal ──────────────────────────────────────────────────────────────

interface ReviewModalProps {
  item: PromotionQueueItem;
  onClose: () => void;
  onPromote: () => void;
  onReject: () => void;
  loading: boolean;
  error?: string | null;
}

function ReviewModal({
  item,
  onClose,
  onPromote,
  onReject,
  loading,
  error,
}: ReviewModalProps) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(item.explanation_text ?? "");
  const [editSaved, setEditSaved] = useState(false);

  const editContentRow = useEditContentRow();

  function handleSaveEdit() {
    editContentRow.mutate(
      { contentId: item.subtopic_content_id, explanationText: editText },
      {
        onSuccess: () => {
          setEditing(false);
          setEditSaved(true);
        },
      },
    );
  }

  const interestLabel = item.interest_category_name
    ? (INTEREST_LABELS[item.interest_category_name] ??
      item.interest_category_name)
    : null;

  return (
    <Modal
      open
      onOpenChange={onClose}
      title={item.subtopic_name}
      titleClassName="font-['Inter'] font-bold"
    >
      <div className="space-y-4">
        {/* Meta row */}
        <div className="flex items-center gap-2 flex-wrap">
          <ContentTypeBadge type={item.content_type} />
          {interestLabel && (
            <span className="font-['Inter'] text-xs text-role-admin-muted bg-gray-50 border border-role-admin-border px-2 py-0.5 rounded-full">
              {interestLabel}
            </span>
          )}
          <span className="font-['Inter'] text-xs text-role-admin-muted">
            {item.topic_name} · {item.subject_code} · Grade {item.grade_level} ·{" "}
            {item.school_name}
          </span>
        </div>

        {item.reviewed_by_name && (
          <p className="font-['Inter'] text-xs text-role-admin-muted">
            Approved by:{" "}
            <span className="font-semibold text-role-admin-ink">
              {item.reviewed_by_name}
            </span>
          </p>
        )}

        {/* Content area */}
        {item.content_type === "explanation" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted">
                Explanation
              </p>
              {!editing && (
                <button
                  type="button"
                  onClick={() => {
                    setEditText(item.explanation_text ?? "");
                    setEditing(true);
                    setEditSaved(false);
                  }}
                  className="inline-flex items-center gap-1 font-['Inter'] text-xs text-role-admin-muted hover:text-role-admin-ink transition-colors"
                >
                  <Pencil className="w-3 h-3" aria-hidden="true" />
                  Edit
                </button>
              )}
            </div>

            {editing ? (
              <div className="space-y-2">
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  rows={10}
                  className="w-full rounded-lg border border-role-admin-border px-3 py-2 font-['Inter'] text-xs text-role-admin-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 resize-y"
                  aria-label="Edit explanation text"
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(false)}
                    className="px-3 py-1.5 font-['Inter'] text-xs font-medium text-role-admin-ink border border-role-admin-border rounded-full hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEdit}
                    disabled={editContentRow.isPending}
                    className="px-3 py-1.5 font-['Inter'] text-xs font-medium text-white bg-brand-primary rounded-full hover:opacity-90 disabled:opacity-60"
                  >
                    {editContentRow.isPending ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-role-admin-border bg-gray-50 px-3 py-3 max-h-56 overflow-y-auto">
                {editSaved ? (
                  <p className="font-['Inter'] text-xs text-role-admin-ink whitespace-pre-wrap leading-relaxed">
                    {editText}
                  </p>
                ) : item.explanation_text ? (
                  <p className="font-['Inter'] text-xs text-role-admin-ink whitespace-pre-wrap leading-relaxed">
                    {item.explanation_text}
                  </p>
                ) : (
                  <p className="font-['Inter'] text-xs text-role-admin-muted italic">
                    No explanation text available.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {item.content_type === "quiz" && item.quiz_questions && (
          <div className="space-y-2">
            <p className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Quiz — {item.quiz_questions.length} question
              {item.quiz_questions.length !== 1 ? "s" : ""}
            </p>
            <div className="rounded-lg border border-role-admin-border bg-gray-50 px-3 py-3 max-h-64 overflow-y-auto">
              <QuizPreview questions={item.quiz_questions} />
            </div>
          </div>
        )}

        {/* Promotion note */}
        <p className="font-['Inter'] text-xs text-role-admin-muted italic border-t border-role-admin-border pt-3">
          Promoting will convert this content to curriculum-scope (global) and
          make it available to all schools.
        </p>

        {error && (
          <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2">
            <AlertCircle
              className="w-4 h-4 text-red-500 flex-shrink-0"
              aria-hidden="true"
            />
            <p className="font-['Inter'] text-xs text-red-700">{error}</p>
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button
            onClick={onPromote}
            disabled={loading || editing}
            className="flex-1 flex items-center justify-center gap-2 bg-brand-primary text-white rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:opacity-90 disabled:opacity-50"
          >
            <ArrowUpCircle className="w-4 h-4" aria-hidden="true" />
            Promote to Curriculum
          </button>
          <button
            onClick={onReject}
            disabled={loading || editing}
            className="flex-1 flex items-center justify-center gap-2 border border-red-300 text-red-600 rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:bg-red-50 disabled:opacity-50"
          >
            <XCircle className="w-4 h-4" aria-hidden="true" />
            Reject
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Pagination controls ────────────────────────────────────────────────────────

function Pagination({
  page,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between pt-2">
      <p className="font-['Inter'] text-xs text-role-admin-muted">
        {start}–{end} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page === 1}
          className="p-1.5 rounded-lg border border-role-admin-border text-role-admin-muted hover:bg-gray-50 disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
        <span className="font-['Inter'] text-xs text-role-admin-ink px-2">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page === totalPages}
          className="p-1.5 rounded-lg border border-role-admin-border text-role-admin-muted hover:bg-gray-50 disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          aria-label="Next page"
        >
          <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function PromotionQueuePage() {
  const { logout } = useAuth();
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<PromotionQueueItem | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const { data, isLoading } = usePromotionQueue({ page, page_size: PAGE_SIZE });
  const promote = usePromoteContent();

  function handleAction(
    item: PromotionQueueItem,
    action: "promote" | "reject_promotion",
  ) {
    setMutationError(null);
    promote.mutate(
      { contentId: item.subtopic_content_id, action },
      {
        onSuccess: () => setPreview(null),
        onError: () => setMutationError("Action failed. Please try again."),
      },
    );
  }

  return (
    <AdminLayout pageTitle="Promotion Queue" onLogout={logout}>
      <div className="p-6 space-y-6">
        <div>
          <p className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted">
            Content Review
          </p>
          <h1 className="font-['Inter'] text-sm font-bold text-role-admin-ink mt-1">
            Promotion Queue
          </h1>
          <p className="font-['Inter'] text-xs text-role-admin-subtle mt-1">
            School-approved content awaiting promotion to the global curriculum
            library.
          </p>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-role-admin-border rounded-lg" />
            ))}
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-16 px-6">
            <div className="text-4xl mb-4">✅</div>
            <h3 className="font-['Inter'] font-bold text-sm text-role-admin-ink mb-2">
              Queue is clear
            </h3>
            <p className="font-['Inter'] text-xs text-role-admin-subtle">
              No school content is waiting for promotion.
            </p>
          </div>
        ) : (
          <>
            <p className="font-['Inter'] text-xs text-role-admin-muted">
              {data.total} item{data.total !== 1 ? "s" : ""} awaiting review
            </p>
            <div className="bg-white border border-role-admin-border rounded-xl overflow-hidden">
              <table className="w-full text-left">
                <thead className="border-b border-role-admin-border">
                  <tr>
                    {[
                      "Subtopic",
                      "Type",
                      "Interest",
                      "Subject / Grade",
                      "School",
                      "Approved By",
                      "",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-3 font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-role-admin-border">
                  {data.items.map((item) => (
                    <tr
                      key={item.subtopic_content_id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-3 max-w-[200px]">
                        <p className="font-['Inter'] text-xs font-medium text-role-admin-ink truncate">
                          {item.subtopic_name}
                        </p>
                        <p className="font-['Inter'] text-[11px] text-role-admin-muted truncate">
                          {item.topic_name}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <ContentTypeBadge type={item.content_type} />
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {item.interest_category_name
                          ? (INTEREST_LABELS[item.interest_category_name] ??
                            item.interest_category_name)
                          : "—"}
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {item.subject_code} · G{item.grade_level}
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {item.school_name}
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {item.reviewed_by_name ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => {
                            setPreview(item);
                            setMutationError(null);
                          }}
                          className="inline-flex items-center gap-1.5 text-xs font-['Inter'] font-semibold text-brand-primary hover:opacity-80 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
                        >
                          Review
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              page={page}
              total={data.total}
              pageSize={PAGE_SIZE}
              onPage={setPage}
            />
          </>
        )}
      </div>

      {preview && (
        <ReviewModal
          item={preview}
          onClose={() => {
            setPreview(null);
            setMutationError(null);
          }}
          onPromote={() => handleAction(preview, "promote")}
          onReject={() => handleAction(preview, "reject_promotion")}
          loading={promote.isPending}
          error={mutationError}
        />
      )}
    </AdminLayout>
  );
}
