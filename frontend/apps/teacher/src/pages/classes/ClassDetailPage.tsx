import { useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { getSubjectColor } from "@kaihle/types";
import { useClassAssessments } from "../../hooks/useClassAssessments";
import { useClassEnrollments } from "../../hooks/useClassEnrollments";
import { useClass } from "../../hooks/useClass";
import {
  useClassTopics,
  type ClassTopicItem,
} from "../../hooks/useClassTopics";
import { statusBadge } from "../../utils/assessment";
import {
  ArrowLeft,
  Users,
  FileText,
  BookMarked,
  CheckCircle2,
  Clock,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { ClassSetupWizard } from "./ClassSetupWizard";
import { TopicMiniCourseButton } from "../../components/topics/TopicMiniCourseButton";
import { ClassGapMapContent } from "../../components/gap-map/ClassGapMapContent";
import { ClassLessonPlansContent } from "../../components/lesson-plans/ClassLessonPlansContent";
import { SubtopicContentCard } from "../SubtopicContentCard";
import { useTopicSubtopics } from "../../hooks/useSubtopicContent";

type TabId = "gap-map" | "assessments" | "lesson-plans" | "topics" | "students";

// ── Expandable topic row with lazy-loaded subtopics ───────────────────────

function ExpandableTopicRow({
  topic,
  classId,
  curriculumId,
  gradeId,
}: {
  topic: ClassTopicItem;
  classId: string;
  curriculumId: string;
  gradeId: string;
}) {
  const [open, setOpen] = useState(false);
  // topicId + curriculum/grade filters passed only once opened — lazy fetch
  const { data: subtopics, isLoading } = useTopicSubtopics(
    open ? topic.topic_id : null,
    { curriculumId, gradeId },
  );

  return (
    <li className="border-b border-brand-border last:border-b-0">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3 gap-4 hover:bg-gray-50 transition-colors text-left"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2 min-w-0">
          {open ? (
            <ChevronDown
              className="w-4 h-4 text-brand-muted flex-shrink-0"
              aria-hidden="true"
            />
          ) : (
            <ChevronRight
              className="w-4 h-4 text-brand-muted flex-shrink-0"
              aria-hidden="true"
            />
          )}
          <div className="min-w-0">
            <p className="text-sm font-medium text-brand-ink truncate">
              {topic.topic_name}
            </p>
            <p className="text-xs text-brand-muted">
              {topic.subtopic_count} subtopic
              {topic.subtopic_count !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <div onClick={(e) => e.stopPropagation()}>
          <TopicMiniCourseButton topicId={topic.topic_id} classId={classId} />
        </div>
      </button>

      {/* Subtopics panel */}
      {open && (
        <div className="px-5 pb-4 pt-1 space-y-2 bg-gray-50 border-t border-brand-border">
          {isLoading ? (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: topic.subtopic_count || 3 }).map((_, i) => (
                <div key={i} className="h-14 bg-gray-100 rounded-lg" />
              ))}
            </div>
          ) : !subtopics || subtopics.length === 0 ? (
            <p className="text-xs text-brand-muted py-2">No subtopics found.</p>
          ) : (
            subtopics.map((s) => (
              <SubtopicContentCard
                key={s.id}
                subtopicId={s.id}
                classId={classId}
                subtopicName={s.name}
              />
            ))
          )}
        </div>
      )}
    </li>
  );
}

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "gap-map", label: "Gap Map" },
  { id: "assessments", label: "Assessments" },
  { id: "lesson-plans", label: "Lesson Plans" },
  { id: "topics", label: "Topics" },
  { id: "students", label: "Students" },
];

export function ClassDetailPage() {
  const { classId } = useParams<{ classId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: cls, isLoading: classLoading } = useClass(classId);
  const { data: assessments, isLoading: assessmentsLoading } =
    useClassAssessments(classId);
  const { data: students = [], isLoading: studentsLoading } =
    useClassEnrollments(classId);
  const { data: classTopics = [], isLoading: topicsLoading } =
    useClassTopics(classId);

  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardInitialStep, setWizardInitialStep] = useState<1 | 2>(1);

  const activeTab = (searchParams.get("tab") as TabId) ?? "topics";

  function setTab(tab: TabId) {
    setSearchParams(tab === "topics" ? {} : { tab });
  }

  if (classLoading || !cls) {
    return (
      <div className="p-6 animate-pulse">
        <div className="h-4 w-20 bg-gray-200 rounded mb-4" />
        <div className="h-8 w-48 bg-gray-200 rounded mb-6" />
        <div className="grid grid-cols-5 gap-2 mb-8">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  const subjectColor = getSubjectColor(cls.subject_name);
  const studentCount = studentsLoading ? null : students.length;

  const sortedStudents = [...students].sort((a, b) =>
    `${a.first_name} ${a.last_name}`.localeCompare(
      `${b.first_name} ${b.last_name}`,
    ),
  );

  const sortedAssessments = [...(assessments ?? [])].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  const topicsConfigured = !topicsLoading && classTopics.length > 0;
  const hasDiagnostic = (assessments ?? []).some(
    (a) => a.assessment_type === "DIAGNOSTIC",
  );

  function openWizardAtStep(step: 1 | 2) {
    setWizardInitialStep(step);
    setWizardOpen(true);
  }

  return (
    <div className="p-6">
      <Link
        to="/teacher/classes"
        className="inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Classes
      </Link>

      {/* Class header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-3 h-3 rounded-full ${subjectColor}`} />
            <h1 className="font-display font-bold text-2xl text-brand-ink">
              {cls.name}
            </h1>
          </div>
          <div className="flex items-center gap-4 text-sm text-brand-muted">
            <span>{cls.subject_name}</span>
            <span>·</span>
            <span>{cls.grade_name}</span>
            <span>·</span>
            <span>
              {studentCount !== null
                ? `${studentCount} student${studentCount !== 1 ? "s" : ""}`
                : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Setup banners */}
      {!topicsLoading && !topicsConfigured && (
        <div className="flex items-center justify-between bg-[#fffbeb] border-b-2 border-[#fcd34d] px-6 py-[14px] -mx-6 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-[34px] h-[34px] rounded-full bg-brand-gold flex items-center justify-center flex-shrink-0 text-white text-base">
              ✦
            </div>
            <div>
              <p className="text-[13px] font-bold text-[#92400e]">
                This class needs setup before students can begin
              </p>
              <p className="text-[11px] text-[#b45309] mt-0.5">
                Choose your topics and design the Tier 1 diagnostic — takes
                about 5 minutes
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => openWizardAtStep(1)}
            className="flex-shrink-0 ml-6 bg-brand-gold text-white rounded-full px-[18px] py-2 text-xs font-bold hover:bg-brand-gold-dark transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            Set up class →
          </button>
        </div>
      )}

      {topicsConfigured && !hasDiagnostic && (
        <div className="flex items-center justify-between bg-[#fffbeb] border-b-2 border-[#fcd34d] px-6 py-[14px] -mx-6 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-[34px] h-[34px] rounded-full bg-brand-gold flex items-center justify-center flex-shrink-0 text-white text-base">
              ✦
            </div>
            <div>
              <p className="text-[13px] font-bold text-[#92400e]">
                Topics configured — now design the Tier 1 diagnostic
              </p>
              <p className="text-[11px] text-[#b45309] mt-0.5">
                Students will take this on first class entry to map their
                starting knowledge
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => openWizardAtStep(2)}
            className="flex-shrink-0 ml-6 bg-brand-gold text-white rounded-full px-[18px] py-2 text-xs font-bold hover:bg-brand-gold-dark transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            Design diagnostic →
          </button>
        </div>
      )}

      {/* Tab bar */}
      <div
        className="flex gap-0 border-b border-brand-border mb-6"
        role="tablist"
        aria-label="Class sections"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            aria-selected={activeTab === id}
            onClick={() => setTab(id)}
            className={[
              "px-4 py-3 font-sans text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded-t",
              activeTab === id
                ? "text-brand-gold border-b-2 border-brand-gold -mb-px"
                : "text-brand-body hover:text-brand-ink",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Gap Map tab ──────────────────────────────────────────────────── */}
      {activeTab === "gap-map" && (
        <ClassGapMapContent classId={classId!} showExport />
      )}

      {/* ── Assessments tab ──────────────────────────────────────────────── */}
      {activeTab === "assessments" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-semibold text-lg text-brand-ink">
              Assessments
            </h2>
            <Link
              to={`/teacher/classes/${classId}/assessments`}
              className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
            >
              Manage assessments →
            </Link>
          </div>
          {assessmentsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-14 bg-gray-100 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : sortedAssessments.length === 0 ? (
            <div className="text-center py-16 px-6">
              <FileText
                className="w-10 h-10 text-brand-muted mx-auto mb-4"
                aria-hidden="true"
              />
              <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
                No assessments yet
              </h3>
              <p className="text-sm text-brand-body">
                Create your first assessment from the Assessments page.
              </p>
              <Link
                to={`/teacher/classes/${classId}/assessments`}
                className="mt-4 inline-flex items-center gap-2 bg-brand-gold text-white rounded-full px-5 py-2 text-sm font-semibold hover:bg-brand-gold-dark transition-colors"
              >
                Go to Assessments
              </Link>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-brand-border overflow-hidden">
              {sortedAssessments.map((assessment, i) => (
                <div
                  key={assessment.id}
                  className={`flex items-center justify-between px-4 py-3 ${i > 0 ? "border-t border-brand-border" : ""}`}
                >
                  <div>
                    <div className="text-sm font-medium text-brand-ink">
                      {assessment.title}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {statusBadge(assessment.status)}
                      <span className="text-xs text-brand-muted">
                        {assessment.question_count} questions
                      </span>
                    </div>
                  </div>
                  {(assessment.status === "ACTIVE" ||
                    assessment.status === "CLOSED") && (
                    <Link
                      to={`/teacher/assessments/${assessment.id}/results`}
                      className="text-xs font-semibold text-brand-gold hover:text-brand-gold-dark"
                    >
                      Results →
                    </Link>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Lesson Plans tab ─────────────────────────────────────────────── */}
      {activeTab === "lesson-plans" && (
        <ClassLessonPlansContent classId={classId!} />
      )}

      {/* ── Topics tab ───────────────────────────────────────────────────── */}
      {activeTab === "topics" && (
        <div className="space-y-4">
          {topicsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-14 bg-gray-100 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : !topicsConfigured ? (
            <div className="text-center py-16 px-6">
              <BookMarked
                className="w-10 h-10 text-brand-muted mx-auto mb-4"
                aria-hidden="true"
              />
              <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
                No topics configured
              </h3>
              <p className="text-sm text-brand-body mb-4">
                Set up your class to add topics.
              </p>
              <button
                type="button"
                onClick={() => openWizardAtStep(1)}
                className="bg-brand-gold text-white rounded-full px-5 py-2 text-sm font-semibold hover:bg-brand-gold-dark transition-colors"
              >
                Set up class →
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-brand-border overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-brand-border">
                <div className="flex items-center gap-2">
                  <BookMarked
                    className="w-4 h-4 text-brand-primary"
                    aria-hidden="true"
                  />
                  <span className="text-sm font-semibold text-brand-ink">
                    {classTopics.length} topic
                    {classTopics.length !== 1 ? "s" : ""} configured
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => openWizardAtStep(1)}
                  className="text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
                >
                  Edit topics →
                </button>
              </div>
              <ul>
                {classTopics.map((topic) => (
                  <ExpandableTopicRow
                    key={topic.id}
                    topic={topic}
                    classId={classId!}
                    curriculumId={cls.curriculum_id}
                    gradeId={cls.grade_id}
                  />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* ── Students tab ─────────────────────────────────────────────────── */}
      {activeTab === "students" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-semibold text-lg text-brand-ink">
              Enrolled Students
            </h2>
            {!studentsLoading && sortedStudents.length > 0 && (
              <span className="text-xs text-brand-muted">
                {sortedStudents.length} student
                {sortedStudents.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          {studentsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-14 bg-gray-100 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : sortedStudents.length === 0 ? (
            <div className="text-center py-16 px-6">
              <Users
                className="w-10 h-10 text-brand-muted mx-auto mb-4"
                aria-hidden="true"
              />
              <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
                No students enrolled
              </h3>
              <p className="text-sm text-brand-body">
                Students will appear here once enrolled in this class.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-brand-border overflow-hidden">
              {sortedStudents.map((student, i) => (
                <div
                  key={student.id}
                  className={`flex items-center justify-between px-4 py-3 ${i > 0 ? "border-t border-brand-border" : ""}`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-brand-ink">
                      {student.first_name} {student.last_name}
                    </p>
                    <div className="flex items-center gap-3 mt-0.5">
                      {student.diagnostic_completed ? (
                        <span className="inline-flex items-center gap-1 text-xs text-brand-green">
                          <CheckCircle2
                            className="w-3 h-3"
                            aria-hidden="true"
                          />
                          Diagnostic done
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-brand-muted">
                          <Clock className="w-3 h-3" aria-hidden="true" />
                          Awaiting diagnostic
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <Link
                      to={`/teacher/students/${student.id}/profile?tab=mini-courses`}
                      className="text-xs font-semibold text-brand-gold hover:text-brand-gold-dark transition-colors"
                    >
                      Mini-Courses →
                    </Link>
                    <Link
                      to={`/teacher/students/${student.id}/profile`}
                      className="text-xs font-semibold text-brand-body hover:text-brand-ink transition-colors"
                    >
                      Profile →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Wizard */}
      {classId && (
        <ClassSetupWizard
          classId={classId}
          isOpen={wizardOpen}
          onClose={() => setWizardOpen(false)}
          initialStep={wizardInitialStep}
          mode={wizardInitialStep === 1 ? "edit" : "setup"}
        />
      )}
    </div>
  );
}
