import { useState, useMemo } from "react";
import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";
import { useStudentGapMap } from "../../hooks/useStudentGapMap";
import { TopicSection } from "../../components/my-progress/TopicSection";
import { ConceptGuideProvider } from "../../context/ConceptGuideContext";
import { ConceptGuideDrawer } from "../../components/ai/ConceptGuideDrawer";

interface SubjectEntry {
  subjectId: string;
  subjectName: string;
}

export function MyProgress() {
  const { logout } = useAuth();
  const { data: studentInfo } = useStudentInfo();
  const { data: classesData } = useMyClasses();

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  const uniqueSubjects = useMemo<SubjectEntry[]>(() => {
    const seen = new Set<string>();
    const result: SubjectEntry[] = [];
    const safeClasses = Array.isArray(classesData) ? classesData : [];
    for (const cls of safeClasses) {
      if (cls.subjectId && !seen.has(cls.subjectId)) {
        seen.add(cls.subjectId);
        result.push({ subjectId: cls.subjectId, subjectName: cls.subjectName });
      }
    }
    return result;
  }, [classesData]);

  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    uniqueSubjects.length > 0 ? uniqueSubjects[0].subjectId : null,
  );

  const { data: gapMapData, isLoading: isGapMapLoading } = useStudentGapMap(
    selectedSubjectId ?? undefined,
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
        studentName={studentName}
        gradeName={gradeName}
        curriculumName={curriculumName}
        classes={sidebarClasses}
        onLogout={logout}
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
                <div className="bg-brand-amber-light border border-brand-amber/30 rounded-xl p-4 mt-6">
                  <p className="font-sans text-sm text-brand-amber">
                    Take your first assessment to start seeing topic-by-topic
                    progress here.
                  </p>
                </div>
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
