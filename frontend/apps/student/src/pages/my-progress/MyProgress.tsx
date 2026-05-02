import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useStudentGapMap } from "../../hooks/useStudentGapMap";
import { useMyClasses } from "../../hooks/useMyClasses";
import { TopicSection } from "../../components/my-progress/TopicSection";
import { ConceptGuideProvider } from "../../context/ConceptGuideContext";
import { ConceptGuideDrawer } from "../../components/ai/ConceptGuideDrawer";
import { ClipboardList } from "lucide-react";

interface SubjectEntry {
  subjectId: string;
  subjectName: string;
}

export function MyProgress() {
  const layout = useStudentLayoutProps();

  const uniqueSubjects = useMemo<SubjectEntry[]>(() => {
    const seen = new Set<string>();
    const result: SubjectEntry[] = [];
    for (const cls of layout.sidebarClasses) {
      if (cls.subjectId && !seen.has(cls.subjectId)) {
        seen.add(cls.subjectId);
        result.push({ subjectId: cls.subjectId, subjectName: cls.subjectName });
      }
    }
    return result;
  }, [layout.sidebarClasses]);

  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    uniqueSubjects.length > 0 ? uniqueSubjects[0].subjectId : null,
  );

  const { data: gapMapData, isLoading: isGapMapLoading } = useStudentGapMap(
    selectedSubjectId ?? undefined,
  );

  const { data: myClasses = [] } = useMyClasses();

  // Find classes for the selected subject to determine diagnostic status
  const subjectClasses = useMemo(
    () =>
      myClasses.filter((c) => c.subjectId === selectedSubjectId && c.isActive),
    [myClasses, selectedSubjectId],
  );

  // At least one class for this subject has a pending/in-progress diagnostic
  const diagnosticPending = subjectClasses.some(
    (c) => c.onboardingDiagnosticStatus !== "COMPLETED",
  );
  // Find the first class with a pending diagnostic to link to its assessments page
  const pendingDiagnosticClass = subjectClasses.find(
    (c) => c.onboardingDiagnosticStatus !== "COMPLETED",
  );

  const topics = useMemo(() => {
    if (!gapMapData?.scores) return [];

    const topicMap = new Map<
      string,
      {
        topicId: string;
        topicName: string;
        subtopics: {
          subtopicId: string;
          subtopicName: string;
          masteryScore: number | null;
          lastAssessedAt: string | null;
        }[];
      }
    >();

    for (const score of gapMapData.scores) {
      if (!topicMap.has(score.topic_id)) {
        topicMap.set(score.topic_id, {
          topicId: score.topic_id,
          topicName: score.topic_name,
          subtopics: [],
        });
      }
      topicMap.get(score.topic_id)!.subtopics.push({
        subtopicId: score.subtopic_id,
        subtopicName: score.subtopic_name,
        masteryScore: score.mastery_score,
        lastAssessedAt: score.last_assessed_at,
      });
    }

    return Array.from(topicMap.values());
  }, [gapMapData]);

  const selectedSubject = uniqueSubjects.find(
    (s) => s.subjectId === selectedSubjectId,
  );

  return (
    <ConceptGuideProvider>
      <StudentLayout
        activeNav="progress"
        studentName={layout.studentName}
        gradeName={layout.gradeName}
        curriculumName={layout.curriculumName}
        classes={layout.sidebarClasses}
        assessmentBadge={layout.assessmentBadge}
        onLogout={layout.onLogout}
      >
        <div className="space-y-6">
          <h1 className="font-display font-bold text-2xl text-brand-ink">
            My Progress
          </h1>

          {uniqueSubjects.length === 0 ? (
            <div className="bg-white rounded-xl border border-brand-border p-8 text-center">
              <p className="text-brand-muted">
                You are not enrolled in any subjects yet.
              </p>
            </div>
          ) : (
            <>
              <div className="flex gap-2 flex-wrap">
                {uniqueSubjects.map((subject) => (
                  <button
                    key={subject.subjectId}
                    type="button"
                    onClick={() => setSelectedSubjectId(subject.subjectId)}
                    className={`px-4 py-2 rounded-lg font-sans text-sm font-medium transition-colors ${
                      selectedSubjectId === subject.subjectId
                        ? "bg-brand-primary text-white"
                        : "bg-white border border-brand-border text-brand-ink hover:bg-brand-bg"
                    }`}
                  >
                    {subject.subjectName}
                  </button>
                ))}
              </div>

              {isGapMapLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-16 bg-brand-border/50 rounded-xl animate-pulse"
                    />
                  ))}
                </div>
              ) : topics.length === 0 ? (
                diagnosticPending ? (
                  <div className="flex items-start gap-4 bg-white border border-role-student-border rounded-xl p-5 mt-6">
                    <div className="w-10 h-10 rounded-full bg-brand-green-light flex items-center justify-center flex-shrink-0">
                      <ClipboardList
                        className="w-5 h-5 text-brand-primary"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm text-brand-ink mb-1">
                        Diagnostic pending
                      </p>
                      <p className="text-xs text-brand-body leading-relaxed">
                        Your progress map will appear here once you complete the
                        Tier 1 diagnostic for{" "}
                        <strong>{selectedSubject?.subjectName}</strong>. You can
                        access content in the meantime.
                      </p>
                      {pendingDiagnosticClass && (
                        <Link
                          to={`/student/classes/${pendingDiagnosticClass.id}/diagnostic`}
                          className="inline-block mt-3 text-xs font-semibold text-brand-primary hover:text-brand-primary/80 transition-colors"
                        >
                          Take diagnostic →
                        </Link>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="bg-brand-amber-light border border-brand-amber/30 rounded-xl p-4 mt-6">
                    <p className="font-sans text-sm text-brand-amber">
                      Take your first assessment to start seeing topic-by-topic
                      progress here.
                    </p>
                  </div>
                )
              ) : (
                <div className="space-y-4">
                  <h2 className="font-sans text-section-label font-bold uppercase tracking-[0.8px] text-brand-body">
                    {selectedSubject?.subjectName} — Topic Breakdown
                  </h2>
                  <div className="space-y-3">
                    {topics.map((topic) => (
                      <TopicSection
                        key={topic.topicId}
                        topicName={topic.topicName}
                        subtopics={topic.subtopics}
                        defaultExpanded={false}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </StudentLayout>
      <ConceptGuideDrawer />
    </ConceptGuideProvider>
  );
}
