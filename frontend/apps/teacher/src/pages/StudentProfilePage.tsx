import { useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { useStudentProfile } from "../hooks/useStudentProfile";
import { StudentProfileHeader } from "../components/students/StudentProfileHeader";
import { LearningStyleCard } from "../components/students/LearningStyleCard";
import { GapProfileSection } from "../components/students/GapProfileSection";

export function StudentProfilePage() {
  const { studentId } = useParams<{ studentId: string }>();
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data, isLoading, isError } = useStudentProfile(
    studentId ?? null,
    schoolId,
  );
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    null,
  );

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="h-4 w-32 bg-gray-100 rounded" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-64 bg-gray-100 rounded-xl animate-pulse" />
          <div className="h-48 bg-gray-100 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <div className="text-red-600 p-4 bg-red-50 rounded-lg">
          Failed to load student profile. Please try again.
        </div>
      </div>
    );
  }

  const filteredGapMap = data.gapMap
    ? {
        ...data.gapMap,
        scores: selectedSubjectId
          ? data.gapMap.scores.filter((s) => s.topic_id === selectedSubjectId)
          : data.gapMap.scores,
      }
    : null;

  const avgMastery =
    filteredGapMap && filteredGapMap.scores.length > 0
      ? filteredGapMap.scores.reduce(
          (sum, s) => sum + (s.mastery_score ?? 0),
          0,
        ) / filteredGapMap.scores.filter((s) => s.mastery_score !== null).length
      : null;

  return (
    <div className="p-6 space-y-6">
      <StudentProfileHeader
        name={data.studentName}
        email={data.email}
        className={data.className}
        avgMastery={avgMastery}
      />

      {data.availableSubjects.length > 1 && (
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-brand-muted">Subject:</span>
          <div className="flex flex-wrap gap-2">
            {data.availableSubjects.map((subject) => (
              <button
                key={subject.subjectId}
                type="button"
                onClick={() => setSelectedSubjectId(subject.subjectId)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  selectedSubjectId === subject.subjectId ||
                  (!selectedSubjectId &&
                    subject.subjectId === filteredGapMap?.subject_id)
                    ? "bg-brand-primary text-white"
                    : "bg-gray-100 text-brand-muted hover:bg-gray-200"
                }`}
              >
                {subject.subjectName}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setSelectedSubjectId(null)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                selectedSubjectId === null
                  ? "bg-brand-primary text-white"
                  : "bg-gray-100 text-brand-muted hover:bg-gray-200"
              }`}
            >
              All Subjects
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <GapProfileSection gapMap={filteredGapMap} />
        </div>
        <div className="space-y-6">
          <LearningStyleCard
            modalityScores={data.learningProfile?.modality_scores ?? {}}
            interests={data.learningProfile?.interests ?? []}
          />
          <div className="bg-white rounded-2xl border border-brand-border shadow-sm p-5">
            <h2 className="font-display font-semibold text-lg text-brand-ink mb-4">
              Study Plan History
            </h2>
            <p className="text-sm text-brand-muted italic">
              Study plan history will appear here once M3 is complete.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
