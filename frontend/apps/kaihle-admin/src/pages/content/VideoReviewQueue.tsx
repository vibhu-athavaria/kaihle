import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useReviewQueue,
  type ReviewQueueItem,
} from "../../hooks/useSubtopicContent";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { BookOpen } from "lucide-react";

// ── Status pill ─────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: string | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-role-admin-muted">
        — not seeded
      </span>
    );
  }
  const map: Record<string, string> = {
    pending: "bg-amber-50 text-amber-700 border border-amber-200",
    approved: "bg-green-50 text-brand-primary border border-green-200",
    rejected: "bg-red-50 text-red-700 border border-red-200",
  };
  const label: Record<string, string> = {
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-100 text-gray-600"}`}
    >
      {label[status] ?? status}
    </span>
  );
}

// ── Overall row completion badge ────────────────────────────────────────────

function rowBadge(item: ReviewQueueItem): { label: string; cls: string } {
  const statuses = [
    item.video_status,
    item.explanation_status,
    item.quiz_status,
  ].filter(Boolean);
  if (statuses.length === 0)
    return { label: "Empty", cls: "text-role-admin-muted" };
  if (statuses.every((s) => s === "approved"))
    return { label: "✓ Complete", cls: "text-brand-primary font-semibold" };
  if (statuses.some((s) => s === "pending"))
    return { label: "● Needs review", cls: "text-amber-600" };
  return { label: "⊘ Rejected", cls: "text-red-600" };
}

// ── Skeleton row ────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr className="animate-pulse">
      {[48, 16, 12, 24, 24, 24, 24].map((w, i) => (
        <td key={i} className="px-4 py-3">
          <div className={`h-4 bg-gray-200 rounded w-${w}`} />
        </td>
      ))}
    </tr>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export function ContentReviewQueue() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [subject, setSubject] = useState<string>("");
  const [grade, setGrade] = useState<string>("");
  const [status, setStatus] = useState<"all" | "pending" | "complete">("all");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useReviewQueue({
    subject: subject || undefined,
    grade: grade ? parseInt(grade, 10) : undefined,
    status,
    page,
    page_size: 20,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pendingTotal = data?.pending_total ?? 0;

  const handleRowClick = (subtopicId: string) => {
    navigate(`/kaihle-admin/content/review/${subtopicId}`);
  };

  return (
    <AdminLayout pageTitle="Subtopic Content Review" onLogout={logout}>
      <div className="p-6">
        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-brand-primary" />
            Subtopic Content Review
          </h1>
          <p className="text-xs text-role-admin-muted mt-1">
            {pendingTotal > 0
              ? `${pendingTotal} items pending review across ${total} subtopics`
              : `${total} subtopics seeded`}
          </p>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex items-center gap-2">
            <label
              htmlFor="filter-subject"
              className="text-xs text-gray-500 font-medium"
            >
              Subject
            </label>
            <select
              id="filter-subject"
              value={subject}
              onChange={(e) => {
                setSubject(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
            >
              <option value="">All</option>
              <option value="MATH">MATH</option>
              <option value="SCI">SCI</option>
              <option value="BIO">BIO</option>
              <option value="CHEM">CHEM</option>
              <option value="PHY">PHY</option>
              <option value="ENG">ENG</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label
              htmlFor="filter-grade"
              className="text-xs text-gray-500 font-medium"
            >
              Grade
            </label>
            <select
              id="filter-grade"
              value={grade}
              onChange={(e) => {
                setGrade(e.target.value);
                setPage(1);
              }}
              className="text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
            >
              <option value="">All</option>
              {[6, 7, 8, 9, 10, 11, 12].map((g) => (
                <option key={g} value={String(g)}>
                  Gr.{g}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <label className="text-xs text-gray-500 font-medium">Status</label>
            <div className="inline-flex rounded-md border border-gray-300 overflow-hidden bg-white">
              {(["all", "pending", "complete"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setStatus(s);
                    setPage(1);
                  }}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    status === s
                      ? "bg-brand-primary text-white"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {s === "all"
                    ? "All"
                    : s === "pending"
                      ? "Needs Review"
                      : "Complete"}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Subtopic
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Subject
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Grade
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Video
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Explanation
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Quiz
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Overall
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : isError ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center text-sm text-red-600"
                  >
                    Failed to load review queue. Please try again.
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center text-sm text-gray-500"
                  >
                    No subtopics found. Run the seed script first, or adjust
                    your filters.
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const badge = rowBadge(item);
                  return (
                    <tr
                      key={String(item.subtopic_id)}
                      onClick={() => handleRowClick(String(item.subtopic_id))}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 text-sm text-gray-900 font-medium max-w-[200px] truncate">
                        {item.subtopic_name}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {item.subject_code}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        Gr.{item.grade_level}
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={item.video_status} />
                        {item.video_status === "pending" &&
                          item.pending_video_count > 0 && (
                            <span className="ml-1.5 text-xs text-role-admin-muted">
                              {item.pending_video_count} pending
                            </span>
                          )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={item.explanation_status} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={item.quiz_status} />
                      </td>
                      <td className={`px-4 py-3 text-xs ${badge.cls}`}>
                        {badge.label}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 20 && (
          <div className="flex items-center justify-between mt-4">
            <p className="text-xs text-gray-500">
              Page {page} — {total} total subtopics
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                disabled={items.length < 20}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
