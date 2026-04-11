import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useReviewQueue } from "../../hooks/useSubtopicContent";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { PlaySquare } from "lucide-react";

// ── Status helpers ──────────────────────────────────────────────────────────

type QueueStatus = "all" | "pending" | "complete";

function rowStatus(item: {
  pending_video_count: number;
  approved_video_count: number;
}): { label: string; cls: string } {
  if (item.approved_video_count > 0 && item.pending_video_count === 0) {
    return { label: "✓ Done", cls: "text-brand-primary" };
  }
  if (item.pending_video_count > 0 && item.approved_video_count === 0) {
    return { label: "● Pending", cls: "text-brand-amber" };
  }
  return { label: "● Partial", cls: "text-brand-gold" };
}

// ── Skeleton row ────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-40" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-16" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-12" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-20" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-24" />
      </td>
    </tr>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export function VideoReviewQueue() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [subject, setSubject] = useState<string>("");
  const [grade, setGrade] = useState<string>("");
  const [status, setStatus] = useState<QueueStatus>("all");
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
    navigate(`/kaihle-admin/content/videos/${subtopicId}`);
  };

  return (
    <AdminLayout pageTitle="Video Library Review" onLogout={logout}>
      <div className="p-6">
        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <PlaySquare className="w-4 h-4 text-brand-primary" />
            Video Library Review
          </h1>
          {pendingTotal > 0 ? (
            <p className="text-xs text-role-admin-muted mt-1">
              {pendingTotal} videos pending review across {total} subtopics
            </p>
          ) : (
            <p className="text-xs text-role-admin-muted mt-1">
              {total} subtopics
            </p>
          )}
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
                      ? "Pending"
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
                  Videos
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : isError ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm text-red-600"
                  >
                    Failed to load review queue. Please try again.
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm text-gray-500"
                  >
                    No subtopics found matching your filters.
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const statusInfo = rowStatus(item);
                  return (
                    <tr
                      key={item.subtopic_id}
                      onClick={() => handleRowClick(item.subtopic_id)}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 text-sm text-gray-900 font-medium">
                        {item.subtopic_name}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {item.subject_code}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        Gr.{item.grade_level}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {item.approved_video_count}/
                        {item.approved_video_count + item.pending_video_count} ✓
                      </td>
                      <td
                        className={`px-4 py-3 text-sm font-medium ${statusInfo.cls}`}
                      >
                        {statusInfo.label}
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
