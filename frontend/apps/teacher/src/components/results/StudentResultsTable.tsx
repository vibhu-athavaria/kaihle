/**
 * StudentResultsTable — table of student results for an assessment.
 *
 * Default sort: score ascending (lowest first) — teacher sees struggling students first.
 * Features: search (debounced 150ms), sort dropdown, score pills, "View answers" links.
 * Score pills use getMasteryStyle. "Pending" for not-submitted students.
 */
import { useState, useMemo, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { getMasteryStyle } from "@kaihle/types";
import type { StudentAttemptSummary } from "../../hooks/useAssessmentResults";

type SortOption = "score-asc" | "score-desc" | "name-asc" | "date-submitted";

interface StudentResultsTableProps {
  assessmentId: string;
  attempts: StudentAttemptSummary[];
  isLoading?: boolean;
}

function ScorePill({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <span className="rounded-full px-3 py-1 text-sm bg-gray-100 text-gray-400">
        Pending
      </span>
    );
  }
  const { textClass, bgClass, label } = getMasteryStyle(score);
  return (
    <span
      className={`rounded-full px-3 py-1 text-sm font-semibold ${textClass} ${bgClass}`}
    >
      {Math.round(score * 100)}% · {label}
    </span>
  );
}

export function StudentResultsTable({
  assessmentId,
  attempts,
  isLoading = false,
}: StudentResultsTableProps) {
  const [rawSearch, setRawSearch] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortOption>("score-asc");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search 150ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(rawSearch), 150);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [rawSearch]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return q
      ? attempts.filter((a) => a.studentName.toLowerCase().includes(q))
      : attempts;
  }, [attempts, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    switch (sort) {
      case "score-asc":
        return arr.sort((a, b) => (a.score ?? -1) - (b.score ?? -1));
      case "score-desc":
        return arr.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
      case "name-asc":
        return arr.sort((a, b) => a.studentName.localeCompare(b.studentName));
      case "date-submitted":
        return arr.sort((a, b) => {
          if (!a.submittedAt && !b.submittedAt) return 0;
          if (!a.submittedAt) return 1;
          if (!b.submittedAt) return -1;
          return (
            new Date(b.submittedAt).getTime() -
            new Date(a.submittedAt).getTime()
          );
        });
      default:
        return arr;
    }
  }, [filtered, sort]);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-14 bg-gray-100 rounded-xl" />
        ))}
      </div>
    );
  }

  if (attempts.length === 0) {
    return (
      <div className="text-center py-16 px-6 bg-gray-50 rounded-xl">
        <div className="text-4xl mb-4">📋</div>
        <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
          No students enrolled
        </h3>
        <p className="text-brand-body text-sm max-w-sm mx-auto">
          Students will appear here once they are enrolled in this class.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="search"
          placeholder="Search students…"
          value={rawSearch}
          onChange={(e) => setRawSearch(e.target.value)}
          className="flex-1 border border-role-teacher-border rounded-lg px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 focus:outline-none"
          aria-label="Search students by name"
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortOption)}
          className="border border-role-teacher-border rounded-lg px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 focus:outline-none"
          aria-label="Sort results"
        >
          <option value="score-asc">Score ↑ (lowest first)</option>
          <option value="score-desc">Score ↓ (highest first)</option>
          <option value="name-asc">Name A–Z</option>
          <option value="date-submitted">Date submitted</option>
        </select>
      </div>

      {/* Table */}
      {sorted.length === 0 ? (
        <div className="text-center py-10 text-brand-muted text-sm">
          No students match your search.
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-widest text-brand-muted">
                  Student
                </th>
                <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-widest text-brand-muted">
                  Score
                </th>
                <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-widest text-brand-muted hidden sm:table-cell">
                  Submitted
                </th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sorted.map((attempt) => (
                <tr
                  key={attempt.attemptId}
                  className="hover:bg-gray-50 transition-colors min-h-[56px]"
                >
                  <td className="px-5 py-4 font-sans text-sm font-medium text-brand-ink">
                    {attempt.studentName}
                  </td>
                  <td className="px-5 py-4">
                    <ScorePill score={attempt.score} />
                  </td>
                  <td className="px-5 py-4 text-sm text-brand-muted hidden sm:table-cell">
                    {attempt.submittedAt
                      ? new Date(attempt.submittedAt).toLocaleDateString(
                          "en-GB",
                          {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          },
                        )
                      : "—"}
                  </td>
                  <td className="px-5 py-4 text-right">
                    {attempt.status === "SUBMITTED" ? (
                      <Link
                        to={`/teacher/assessments/${assessmentId}/results/${attempt.studentId}?attempt=${attempt.attemptId}`}
                        className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded"
                      >
                        View answers →
                      </Link>
                    ) : (
                      <span className="text-sm text-brand-muted">
                        Not submitted
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
