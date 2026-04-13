import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { useStudentProfile } from "../hooks/useStudentProfile";
import { useStudentGapMapForTeacher } from "../hooks/useStudentGapMapForTeacher";
import { StudentProfileHeader } from "../components/students/StudentProfileHeader";
import { SubjectMasteryCards } from "../components/students/SubjectMasteryCards";
import { StudentGapMapTab } from "../components/students/StudentGapMapTab";
import { LearningProfileTab } from "../components/students/LearningProfileTab";
import { StudyPlanHistoryTab } from "../components/students/StudyPlanHistoryTab";
import { AssessmentHistoryTab } from "../components/students/AssessmentHistoryTab";

type TabId = "gap-map" | "learning-profile" | "study-plans" | "assessments";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "gap-map", label: "Gap Map" },
  { id: "learning-profile", label: "Learning Profile" },
  { id: "study-plans", label: "Study Plans" },
  { id: "assessments", label: "Assessments" },
];

export function StudentProfilePage() {
  const { studentId } = useParams<{ studentId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data, isLoading, isError } = useStudentProfile(
    studentId ?? null,
    schoolId,
  );
  const activeTab = (searchParams.get("tab") as TabId) ?? "gap-map";
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    null,
  );

  const subjectId =
    selectedSubjectId ?? data?.availableSubjects[0]?.subjectId ?? null;
  const { data: gapMap } = useStudentGapMapForTeacher(
    studentId ?? null,
    subjectId,
  );

  const handleTabChange = (tab: TabId) => {
    setSearchParams({ tab });
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="h-4 w-32 bg-gray-100 rounded" />
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

  const subjectMasteryCards = data.availableSubjects.map((s) => ({
    subjectId: s.subjectId,
    subjectName: s.subjectName,
    avgMastery: null as number | null,
  }));

  return (
    <div className="space-y-0">
      <div className="p-6 pb-4">
        <StudentProfileHeader
          name={data.studentName}
          email={data.email}
          className={data.className}
          avgMastery={null}
        />
      </div>

      {subjectMasteryCards.length > 0 && (
        <div className="px-6 py-4">
          <SubjectMasteryCards subjects={subjectMasteryCards} />
        </div>
      )}

      {/* Tab nav */}
      <div className="sticky top-0 z-10 bg-white border-b border-brand-border">
        <nav className="flex px-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleTabChange(tab.id)}
              className={`px-4 py-3 text-sm font-sans font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-b-2 border-brand-gold text-brand-gold"
                  : "text-brand-muted hover:text-brand-ink"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="p-6">
        {activeTab === "gap-map" && (
          <>
            {data.availableSubjects.length > 1 && (
              <div className="flex gap-2 mb-4 flex-wrap">
                {data.availableSubjects.map((s) => (
                  <button
                    key={s.subjectId}
                    type="button"
                    onClick={() => setSelectedSubjectId(s.subjectId)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      (selectedSubjectId ??
                        data.availableSubjects[0]?.subjectId) === s.subjectId
                        ? "bg-brand-light text-brand-primary border border-brand-primary"
                        : "bg-gray-100 text-brand-muted hover:bg-gray-200"
                    }`}
                  >
                    {s.subjectName}
                  </button>
                ))}
              </div>
            )}
            <StudentGapMapTab scores={gapMap?.scores ?? []} />
          </>
        )}

        {activeTab === "learning-profile" && data.learningProfile && (
          <LearningProfileTab
            modalityScores={data.learningProfile.modality_scores}
            interests={data.learningProfile.interests}
          />
        )}
        {activeTab === "learning-profile" && !data.learningProfile && (
          <p className="text-sm text-brand-muted italic text-center py-12">
            This student hasn't completed their learning profile yet.
          </p>
        )}
        {activeTab === "study-plans" && <StudyPlanHistoryTab />}
        {activeTab === "assessments" && <AssessmentHistoryTab />}
      </div>
    </div>
  );
}
