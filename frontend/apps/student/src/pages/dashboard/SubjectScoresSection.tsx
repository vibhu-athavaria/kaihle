import { useEffect, useState, useCallback } from "react";
import {
  useSubjectGapMap,
  aggregateSubjectMastery,
} from "../../hooks/useSubjectScores";
import { SubjectScoreCard } from "./SubjectScoreCard";

export interface SubjectEntry {
  subjectId: string;
  subjectName: string;
}

export interface ResolvedSubjectScore {
  subjectName: string;
  avgMastery: number | null;
}

interface SubjectScoresSectionProps {
  /** Unique subjects derived from enrolled classes */
  subjects: SubjectEntry[];
  /** Optional callback fired when all subject scores are resolved */
  onScoresResolved?: (scores: ResolvedSubjectScore[]) => void;
}

/**
 * Wrapper component that fetches score and reports it via callback
 */
interface SingleSubjectCardWithCallbackProps {
  subject: SubjectEntry;
  onResolved: (score: number | null) => void;
}

function SingleSubjectCardWithCallback({
  subject,
  onResolved,
}: SingleSubjectCardWithCallbackProps) {
  const { data, isLoading } = useSubjectGapMap(subject.subjectId);
  const avgMastery = aggregateSubjectMastery(data);

  // Report score when loading completes
  useEffect(() => {
    if (!isLoading) {
      onResolved(avgMastery);
    }
  }, [isLoading, avgMastery, onResolved]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-role-student-border p-4 animate-pulse h-[96px]" />
    );
  }

  return (
    <SubjectScoreCard subjectName={subject.subjectName} score={avgMastery} />
  );
}

/**
 * Subject scores section for the student dashboard.
 * Renders a grid of subject score cards, one per enrolled subject.
 *
 * When onScoresResolved is provided, calls it with the aggregated scores
 * once all queries have settled (no longer loading).
 */
export function SubjectScoresSection({
  subjects,
  onScoresResolved,
}: SubjectScoresSectionProps) {
  const [resolvedScores, setResolvedScores] = useState<ResolvedSubjectScore[]>(
    [],
  );
  const [hasCalledCallback, setHasCalledCallback] = useState(false);

  // Reset resolved scores when subjects change
  useEffect(() => {
    setResolvedScores([]);
    setHasCalledCallback(false);
  }, [subjects]);

  // Call onScoresResolved when all subjects have resolved - only once
  useEffect(() => {
    if (!onScoresResolved || hasCalledCallback) return;

    // Check if all subjects have resolved
    const allResolved =
      subjects.length > 0 &&
      subjects.every((subject) =>
        resolvedScores.some((s) => s.subjectName === subject.subjectName),
      );

    if (allResolved && resolvedScores.length > 0) {
      onScoresResolved(resolvedScores);
      setHasCalledCallback(true);
    }
  }, [resolvedScores, subjects, onScoresResolved, hasCalledCallback]);

  if (!subjects.length) return null;

  const handleResolved = useCallback(
    (subjectName: string, score: number | null) => {
      setResolvedScores((prev) => {
        // Don't add duplicates
        if (prev.some((s) => s.subjectName === subjectName)) {
          return prev;
        }
        return [...prev, { subjectName, avgMastery: score }];
      });
    },
    [],
  );

  return (
    <div className="mb-6">
      <h2 className="font-sans text-section-label font-bold uppercase tracking-[0.8px] text-brand-body mb-2.5">
        Your subjects
      </h2>
      <div className="grid grid-cols-3 gap-3">
        {subjects.map((subject) => (
          <SingleSubjectCardWithCallback
            key={subject.subjectId}
            subject={subject}
            onResolved={(score) => handleResolved(subject.subjectName, score)}
          />
        ))}
      </div>
    </div>
  );
}
