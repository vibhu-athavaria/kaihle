import { useState } from "react";
import { AdminLayout, Modal, Skeleton, Badge } from "@kaihle/ui";
import { Check, X, Edit3, AlertCircle } from "lucide-react";
import {
  useQuestionReviewItems,
  useApproveReviewItem,
  useRejectReviewItem,
  type QuestionReviewItem,
  type ReviewItemType,
} from "../../hooks/useQuestionReview";

const TYPE_TABS: Array<{ value: ReviewItemType | undefined; label: string }> = [
  { value: undefined, label: "All" },
  { value: "TEACHER_QUESTION", label: "New Questions" },
  { value: "EDIT_SUGGESTION", label: "Edit Suggestions" },
];

function DiffRow({
  label,
  original,
  suggested,
}: {
  label: string;
  original: string | null;
  suggested: string | null;
}) {
  if (!suggested || suggested === original) return null;
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400">
        {label}
      </p>
      <div className="bg-red-50 border border-red-200 rounded-lg p-2">
        <p className="text-xs font-['Inter'] text-red-700 line-through">
          {original}
        </p>
      </div>
      <div className="bg-green-50 border border-green-200 rounded-lg p-2">
        <p className="text-xs font-['Inter'] text-green-700">{suggested}</p>
      </div>
    </div>
  );
}

interface ReviewModalProps {
  item: QuestionReviewItem;
  onClose: () => void;
}

function ReviewModal({ item, onClose }: ReviewModalProps) {
  const [editMode, setEditMode] = useState(false);
  const [editedText, setEditedText] = useState(
    item.suggested_question_text ?? item.question_text,
  );
  const [editedAnswer, setEditedAnswer] = useState(
    item.suggested_correct_answer ?? item.correct_answer,
  );
  const [adminNote, setAdminNote] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const approveMutation = useApproveReviewItem();
  const rejectMutation = useRejectReviewItem();

  async function handleApprove() {
    setErrorMsg(null);
    const payload = editMode
      ? {
          question_text: editedText,
          correct_answer: editedAnswer,
        }
      : item.item_type === "EDIT_SUGGESTION"
        ? {
            question_text: item.suggested_question_text ?? undefined,
            correct_answer: item.suggested_correct_answer ?? undefined,
            explanation: item.suggested_explanation ?? undefined,
            difficulty_level: item.suggested_difficulty_level ?? undefined,
          }
        : undefined;
    try {
      await approveMutation.mutateAsync({ itemId: item.id, payload });
      onClose();
    } catch {
      setErrorMsg("Failed to approve. Please try again.");
    }
  }

  async function handleReject() {
    setErrorMsg(null);
    try {
      await rejectMutation.mutateAsync({
        itemId: item.id,
        payload: adminNote ? { admin_note: adminNote } : undefined,
      });
      onClose();
    } catch {
      setErrorMsg("Failed to reject. Please try again.");
    }
  }

  const isLoading = approveMutation.isPending || rejectMutation.isPending;
  const isTeacherQuestion = item.item_type === "TEACHER_QUESTION";

  return (
    <div className="space-y-5">
      {/* Meta */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant={isTeacherQuestion ? "gold" : "info"}>
          {isTeacherQuestion ? "New Question" : "Edit Suggestion"}
        </Badge>
        <span className="text-xs font-['Inter'] text-gray-500">
          {item.topic_name} → {item.subtopic_name}
        </span>
        <span className="text-xs font-['Inter'] text-gray-400">
          by {item.submitted_by_name} ({item.school_name})
        </span>
      </div>

      {isTeacherQuestion ? (
        /* Teacher question: show full question, optionally edit */
        <div className="space-y-3">
          <div>
            <p className="text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400 mb-1">
              Question text
            </p>
            {editMode ? (
              <textarea
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 bg-white resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              />
            ) : (
              <p className="text-sm font-['Inter'] text-gray-800">
                {item.question_text}
              </p>
            )}
          </div>
          {item.options && (
            <div>
              <p className="text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400 mb-1">
                Options
              </p>
              {item.options.map((o) => (
                <p
                  key={o.key}
                  className={`text-xs font-['Inter'] ${o.key === item.correct_answer ? "text-green-700 font-semibold" : "text-gray-600"}`}
                >
                  {o.key}. {o.text}
                  {o.key === item.correct_answer && " ✓"}
                </p>
              ))}
            </div>
          )}
          {editMode && (
            <div>
              <p className="text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400 mb-1">
                Correct answer key
              </p>
              <input
                type="text"
                value={editedAnswer}
                onChange={(e) => setEditedAnswer(e.target.value)}
                className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-['Inter'] text-gray-900 bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              />
            </div>
          )}
        </div>
      ) : (
        /* Edit suggestion: show diff */
        <div className="space-y-3">
          <DiffRow
            label="Question text"
            original={item.question_text}
            suggested={item.suggested_question_text}
          />
          <DiffRow
            label="Correct answer"
            original={item.correct_answer}
            suggested={item.suggested_correct_answer}
          />
          <DiffRow
            label="Explanation"
            original={item.explanation}
            suggested={item.suggested_explanation}
          />
          {item.suggested_difficulty_level !== null &&
            item.suggested_difficulty_level !== item.difficulty_level && (
              <div>
                <p className="text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400 mb-1">
                  Difficulty
                </p>
                <p className="text-xs font-['Inter'] text-gray-700">
                  {item.difficulty_level} → {item.suggested_difficulty_level}
                </p>
              </div>
            )}
          {item.reason && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400 mb-1">
                Teacher's reason
              </p>
              <p className="text-xs font-['Inter'] text-gray-700 italic">
                {item.reason}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Admin note for rejection */}
      <div>
        <label
          htmlFor="review-admin-note"
          className="block text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400 mb-1"
        >
          Admin note (optional, shown on reject)
        </label>
        <input
          id="review-admin-note"
          type="text"
          value={adminNote}
          onChange={(e) => setAdminNote(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
          placeholder="Reason for rejection…"
        />
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl p-3">
          <AlertCircle
            className="w-4 h-4 text-red-500 flex-shrink-0"
            aria-hidden="true"
          />
          <p className="text-xs font-['Inter'] text-red-700">{errorMsg}</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        {isTeacherQuestion && (
          <button
            type="button"
            onClick={() => setEditMode((prev) => !prev)}
            className="flex items-center gap-1.5 text-xs font-['Inter'] font-semibold text-gray-500 hover:text-gray-800 transition-colors"
          >
            <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
            {editMode ? "Cancel edits" : "Edit before approving"}
          </button>
        )}
        <div className="flex items-center gap-3 ml-auto">
          <button
            type="button"
            onClick={() => void handleReject()}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-['Inter'] font-bold text-red-600 border border-red-200 bg-red-50 hover:bg-red-100 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
          >
            <X className="w-3.5 h-3.5" aria-hidden="true" />
            Reject
          </button>
          <button
            type="button"
            onClick={() => void handleApprove()}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-['Inter'] font-bold text-white bg-brand-primary hover:bg-brand-primary/90 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            <Check className="w-3.5 h-3.5" aria-hidden="true" />
            {isTeacherQuestion ? "Approve & Promote" : "Apply Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function QuestionReviewPage() {
  const [itemType, setItemType] = useState<ReviewItemType | undefined>(
    undefined,
  );
  const [page, setPage] = useState(1);
  const [selectedItem, setSelectedItem] = useState<QuestionReviewItem | null>(
    null,
  );

  const { data, isLoading, isError } = useQuestionReviewItems(itemType, page);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  function handleTabChange(type: ReviewItemType | undefined) {
    setItemType(type);
    setPage(1);
  }

  return (
    <AdminLayout pageTitle="Question Review">
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="font-['Inter'] font-bold text-xl text-gray-900">
            Question Review Queue
          </h1>
          <p className="text-sm font-['Inter'] text-gray-500 mt-0.5">
            Review teacher-submitted questions and edit suggestions.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-gray-200 pb-0">
          {TYPE_TABS.map((tab) => (
            <button
              key={String(tab.value)}
              type="button"
              onClick={() => handleTabChange(tab.value)}
              className={[
                "px-4 py-2 text-sm font-['Inter'] font-semibold rounded-t-lg border-b-2 transition-colors -mb-px focus-visible:outline-none",
                itemType === tab.value
                  ? "border-brand-primary text-brand-primary bg-brand-primary/5"
                  : "border-transparent text-gray-500 hover:text-gray-800",
              ].join(" ")}
            >
              {tab.label}
              {tab.value === undefined && total > 0 && (
                <span className="ml-1.5 bg-brand-primary text-white text-[10px] font-bold rounded-full px-1.5 py-0.5">
                  {total}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Error state */}
        {isError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl p-4">
            <AlertCircle
              className="w-5 h-5 text-red-500 flex-shrink-0"
              aria-hidden="true"
            />
            <p className="text-sm font-['Inter'] text-red-700">
              Failed to load review queue.
            </p>
          </div>
        )}

        {/* Loading skeletons */}
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && items.length === 0 && (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">✅</div>
            <p className="font-['Inter'] font-bold text-base text-gray-900 mb-1">
              All clear
            </p>
            <p className="text-sm font-['Inter'] text-gray-500">
              No pending items in this queue.
            </p>
          </div>
        )}

        {/* Review items table */}
        {!isLoading && items.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-4 py-3 text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400">
                    Type
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400">
                    Question
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400">
                    Topic
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400">
                    School
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-['Inter'] font-bold uppercase tracking-widest text-gray-400">
                    Submitted
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Badge
                        variant={
                          item.item_type === "TEACHER_QUESTION"
                            ? "gold"
                            : "info"
                        }
                      >
                        {item.item_type === "TEACHER_QUESTION"
                          ? "New Q"
                          : "Edit"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <p className="text-sm font-['Inter'] text-gray-800 truncate">
                        {item.question_text}
                      </p>
                      <p className="text-xs font-['Inter'] text-gray-400">
                        by {item.submitted_by_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs font-['Inter'] text-gray-700">
                        {item.topic_name}
                      </p>
                      <p className="text-xs font-['Inter'] text-gray-400">
                        {item.subtopic_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs font-['Inter'] text-gray-700">
                        {item.school_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs font-['Inter'] text-gray-500">
                        {new Date(item.created_at).toLocaleDateString()}
                      </p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3">
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1.5 text-xs font-['Inter'] font-semibold border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-xs font-['Inter'] text-gray-500">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              disabled={page === totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1.5 text-xs font-['Inter'] font-semibold border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}

        {/* Review modal */}
        <Modal
          open={selectedItem !== null}
          onOpenChange={(open) => {
            if (!open) setSelectedItem(null);
          }}
          title={
            selectedItem?.item_type === "TEACHER_QUESTION"
              ? "Review New Question"
              : "Review Edit Suggestion"
          }
          titleClassName="font-['Inter'] font-bold"
        >
          {selectedItem && (
            <ReviewModal
              key={selectedItem.id}
              item={selectedItem}
              onClose={() => setSelectedItem(null)}
            />
          )}
        </Modal>
      </div>
    </AdminLayout>
  );
}
