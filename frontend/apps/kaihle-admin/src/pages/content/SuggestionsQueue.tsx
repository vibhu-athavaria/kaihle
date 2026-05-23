import { useState } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { Check, X, Edit3 } from "lucide-react";
import {
  useSuggestionsQueue,
  useReviewSuggestion,
  type SuggestionQueueItem,
} from "../../hooks/useSubtopicContent";

interface DiffModalProps {
  item: SuggestionQueueItem;
  onClose: () => void;
  onReview: (
    action: "accept" | "reject" | "accept_with_edits",
    finalText?: string,
    note?: string,
  ) => void;
  loading: boolean;
}

function DiffModal({ item, onClose, onReview, loading }: DiffModalProps) {
  const [editMode, setEditMode] = useState(false);
  const [editedText, setEditedText] = useState(item.suggested_text);
  const [adminNote, setAdminNote] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl mx-4 p-6 space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-['Inter'] text-sm font-bold text-role-admin-ink">
              {item.subtopic_name}
            </h2>
            <p className="font-['Inter'] text-xs text-role-admin-muted mt-0.5">
              Suggested by {item.teacher_name}
              {item.interest_category_name
                ? ` · ${item.interest_category_name}`
                : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-role-admin-muted hover:text-role-admin-ink"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-2">
              Original
            </p>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 min-h-[120px]">
              <p className="font-['Inter'] text-xs text-role-admin-ink whitespace-pre-wrap leading-relaxed">
                {item.original_text}
              </p>
            </div>
          </div>
          <div>
            <p className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-2">
              Suggested
            </p>
            {editMode ? (
              <textarea
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                className="w-full bg-green-50 border border-green-300 rounded-lg p-3 min-h-[120px] font-['Inter'] text-xs text-role-admin-ink resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary"
              />
            ) : (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 min-h-[120px]">
                <p className="font-['Inter'] text-xs text-role-admin-ink whitespace-pre-wrap leading-relaxed">
                  {item.suggested_text}
                </p>
              </div>
            )}
          </div>
        </div>

        <div>
          <label className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted block mb-1">
            Admin note (optional)
          </label>
          <input
            type="text"
            value={adminNote}
            onChange={(e) => setAdminNote(e.target.value)}
            placeholder="Leave a note for the teacher..."
            className="w-full border border-role-admin-border rounded-lg px-3 py-2 font-['Inter'] text-xs text-role-admin-ink focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
        </div>

        <div className="flex gap-3">
          <button
            onClick={() =>
              onReview("accept", undefined, adminNote || undefined)
            }
            disabled={loading}
            className="flex items-center gap-1.5 bg-brand-primary text-white rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:opacity-90 disabled:opacity-50"
          >
            <Check className="w-3.5 h-3.5" aria-hidden="true" />
            Accept
          </button>
          <button
            onClick={() => {
              if (editMode) {
                onReview(
                  "accept_with_edits",
                  editedText,
                  adminNote || undefined,
                );
              } else {
                setEditMode(true);
              }
            }}
            disabled={loading}
            className="flex items-center gap-1.5 border border-role-admin-border text-role-admin-ink rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:bg-gray-50 disabled:opacity-50"
          >
            <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
            {editMode ? "Accept with edits" : "Edit then accept"}
          </button>
          <button
            onClick={() =>
              onReview("reject", undefined, adminNote || undefined)
            }
            disabled={loading}
            className="flex items-center gap-1.5 border border-red-300 text-red-600 rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:bg-red-50 disabled:opacity-50"
          >
            <X className="w-3.5 h-3.5" aria-hidden="true" />
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

export function SuggestionsQueuePage() {
  const { logout } = useAuth();
  const [page] = useState(1);
  const [active, setActive] = useState<SuggestionQueueItem | null>(null);

  const { data, isLoading } = useSuggestionsQueue({ page, page_size: 20 });
  const reviewMutation = useReviewSuggestion();

  function handleReview(
    action: "accept" | "reject" | "accept_with_edits",
    finalText?: string,
    adminNote?: string,
  ) {
    if (!active) return;
    reviewMutation.mutate(
      { suggestionId: active.suggestion_id, action, finalText, adminNote },
      { onSuccess: () => setActive(null) },
    );
  }

  return (
    <AdminLayout pageTitle="Explanation Suggestions" onLogout={logout}>
      <div className="p-6 space-y-6">
        <div>
          <p className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted">
            Content Review
          </p>
          <h1 className="font-['Inter'] text-sm font-bold text-role-admin-ink mt-1">
            Explanation Suggestions
          </h1>
          <p className="font-['Inter'] text-xs text-role-admin-subtle mt-1">
            Teacher-submitted improvements to personalised explanations.
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
            <div className="text-4xl mb-4">💬</div>
            <h3 className="font-['Inter'] font-bold text-sm text-role-admin-ink mb-2">
              No pending suggestions
            </h3>
            <p className="font-['Inter'] text-xs text-role-admin-subtle">
              Teachers haven't submitted any suggestions yet.
            </p>
          </div>
        ) : (
          <>
            <p className="font-['Inter'] text-xs text-role-admin-muted">
              {data.total} pending suggestion{data.total !== 1 ? "s" : ""}
            </p>
            <div className="bg-white border border-role-admin-border rounded-xl overflow-hidden">
              <table className="w-full text-left">
                <thead className="border-b border-role-admin-border">
                  <tr>
                    {["Subtopic", "Category", "Teacher", "Submitted", ""].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-4 py-3 font-['Inter'] text-xs font-bold uppercase tracking-widest text-role-admin-muted"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-role-admin-border">
                  {data.items.map((item) => (
                    <tr
                      key={item.suggestion_id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-ink max-w-[200px] truncate">
                        {item.subtopic_name}
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {item.interest_category_name ?? "—"}
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {item.teacher_name}
                      </td>
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-subtle">
                        {new Date(item.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setActive(item)}
                          className="text-xs font-['Inter'] font-semibold text-brand-primary hover:opacity-80"
                        >
                          Review diff →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {active && (
        <DiffModal
          item={active}
          onClose={() => setActive(null)}
          onReview={handleReview}
          loading={reviewMutation.isPending}
        />
      )}
    </AdminLayout>
  );
}
