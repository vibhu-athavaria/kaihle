import { useState } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { ArrowUpCircle, XCircle, Eye } from "lucide-react";
import {
  usePromotionQueue,
  usePromoteContent,
  type PromotionQueueItem,
} from "../../hooks/useSubtopicContent";

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

interface PreviewModalProps {
  item: PromotionQueueItem;
  onClose: () => void;
  onPromote: () => void;
  onReject: () => void;
  loading: boolean;
}

function PreviewModal({
  item,
  onClose,
  onPromote,
  onReject,
  loading,
}: PreviewModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-['Inter'] text-sm font-bold text-role-admin-ink">
              {item.subtopic_name}
            </h2>
            <p className="font-['Inter'] text-xs text-role-admin-muted mt-0.5">
              {item.subject_code} · Grade {item.grade_level} ·{" "}
              {item.school_name}
            </p>
          </div>
          <ContentTypeBadge type={item.content_type} />
        </div>

        {item.reviewed_by_name && (
          <p className="font-['Inter'] text-xs text-role-admin-muted">
            Approved by teacher:{" "}
            <span className="text-role-admin-ink">{item.reviewed_by_name}</span>
          </p>
        )}

        <p className="font-['Inter'] text-xs text-role-admin-muted italic">
          Promoting will convert this content to curriculum-scope (global) and
          make it available to all schools.
        </p>

        <div className="flex gap-3 pt-2">
          <button
            onClick={onPromote}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 bg-brand-primary text-white rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:opacity-90 disabled:opacity-50"
          >
            <ArrowUpCircle className="w-4 h-4" aria-hidden="true" />
            Promote to Curriculum
          </button>
          <button
            onClick={onReject}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 border border-red-300 text-red-600 rounded-full px-4 py-2 text-xs font-['Inter'] font-semibold hover:bg-red-50 disabled:opacity-50"
          >
            <XCircle className="w-4 h-4" aria-hidden="true" />
            Reject
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-['Inter'] text-role-admin-subtle rounded-full hover:bg-gray-100"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export function PromotionQueuePage() {
  const { logout } = useAuth();
  const [page] = useState(1);
  const [preview, setPreview] = useState<PromotionQueueItem | null>(null);

  const { data, isLoading } = usePromotionQueue({ page, page_size: 20 });
  const promote = usePromoteContent();

  function handleAction(
    item: PromotionQueueItem,
    action: "promote" | "reject_promotion",
  ) {
    promote.mutate(
      { subtopicId: item.subtopic_id, contentType: item.content_type, action },
      { onSuccess: () => setPreview(null) },
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
                      <td className="px-4 py-3 font-['Inter'] text-xs text-role-admin-ink max-w-[200px] truncate">
                        {item.subtopic_name}
                      </td>
                      <td className="px-4 py-3">
                        <ContentTypeBadge type={item.content_type} />
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
                          onClick={() => setPreview(item)}
                          className="inline-flex items-center gap-1.5 text-xs font-['Inter'] font-semibold text-brand-primary hover:opacity-80"
                        >
                          <Eye className="w-3.5 h-3.5" aria-hidden="true" />
                          Review
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

      {preview && (
        <PreviewModal
          item={preview}
          onClose={() => setPreview(null)}
          onPromote={() => handleAction(preview, "promote")}
          onReject={() => handleAction(preview, "reject_promotion")}
          loading={promote.isPending}
        />
      )}
    </AdminLayout>
  );
}
