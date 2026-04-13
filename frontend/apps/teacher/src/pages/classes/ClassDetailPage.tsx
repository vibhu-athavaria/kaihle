import { useParams, Link } from "react-router-dom";
import { getMasteryStyle, scoreToPercent, getSubjectColor } from "@kaihle/types";
import { useClassAssessments } from "../../hooks/useClassAssessments";
import { useMyStudents } from "../../hooks/useMyStudents";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { useAuth } from "@kaihle/auth";
import { statusBadge } from "../../utils/assessment";
import { ArrowLeft, Users, BarChart2, FileText, BookOpen } from "lucide-react";

export function ClassDetailPage() {
  const { classId } = useParams<{ classId: string }>();
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data: dashboardData, isLoading: dashboardLoading } =
    useTeacherDashboard(schoolId);
  const { data: assessments, isLoading: assessmentsLoading } =
    useClassAssessments(classId);
  const { data: students, isLoading: studentsLoading } = useMyStudents(
    classId ? [classId] : [],
    [],
  );

  const cls = dashboardData?.classes.find((c) => c.id === classId);

  if (dashboardLoading || !cls) {
    return (
      <div className="p-6 animate-pulse">
        <div className="h-4 w-20 bg-gray-200 rounded mb-4" />
        <div className="h-8 w-48 bg-gray-200 rounded mb-6" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-gray-200 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const { dotClass, textClass, label } = getMasteryStyle(cls.avgMastery);
  const displayPct = scoreToPercent(cls.avgMastery);
  const subjectColor = getSubjectColor(cls.subjectName);

  const sortedStudents = [...(students ?? [])]
    .sort((a, b) => (a.avgMastery ?? -1) - (b.avgMastery ?? -1))
    .slice(0, 5);

  const recentAssessments = [...(assessments ?? [])]
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    .slice(0, 3);

  return (
    <div className="p-6">
      <Link
        to="/teacher/classes"
        className="inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Classes
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-3 h-3 rounded-full ${subjectColor}`} />
            <h1 className="font-display font-bold text-2xl text-brand-ink">
              {cls.name}
            </h1>
          </div>
          <div className="flex items-center gap-4 text-sm text-brand-muted">
            <span>{cls.subjectName}</span>
            <span>·</span>
            <span>{cls.gradeName}</span>
            <span>·</span>
            <span>
              {cls.studentCount} student{cls.studentCount !== 1 ? "s" : ""}
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${dotClass}`} />
              <span className={`font-semibold ${textClass}`}>{displayPct}</span>
              <span>{label}</span>
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Link
          to={`/teacher/classes/${classId}/gap-map`}
          className="bg-white rounded-xl border border-brand-border p-4 hover:shadow-card-hover transition-all"
        >
          <Users className="w-5 h-5 text-brand-gold mb-2" />
          <div className="text-sm font-semibold text-brand-ink">Gap Map</div>
          <div className="text-xs text-brand-muted">
            See where each student is struggling
          </div>
        </Link>
        <Link
          to={`/teacher/classes/${classId}/assessments`}
          className="bg-white rounded-xl border border-brand-border p-4 hover:shadow-card-hover transition-all"
        >
          <BarChart2 className="w-5 h-5 text-brand-gold mb-2" />
          <div className="text-sm font-semibold text-brand-ink">
            Assessments
          </div>
          <div className="text-xs text-brand-muted">
            Create and manage assessments
          </div>
        </Link>
        <Link
          to={`/teacher/classes/${classId}/study-plan`}
          className="bg-white rounded-xl border border-brand-border p-4 hover:shadow-card-hover transition-all"
        >
          <FileText className="w-5 h-5 text-brand-gold mb-2" />
          <div className="text-sm font-semibold text-brand-ink">Study Plan</div>
          <div className="text-xs text-brand-muted">
            Personalised study plans
          </div>
        </Link>
        <Link
          to={`/teacher/classes/${classId}/lesson-plans`}
          className="bg-white rounded-xl border border-brand-border p-4 hover:shadow-card-hover transition-all"
        >
          <BookOpen className="w-5 h-5 text-brand-gold mb-2" />
          <div className="text-sm font-semibold text-brand-ink">
            Lesson Plans
          </div>
          <div className="text-xs text-brand-muted">AI-generated lesson plans</div>
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h2 className="font-display font-semibold text-lg text-brand-ink mb-3">
            Students at Risk
          </h2>
          {studentsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : sortedStudents.length === 0 ? (
            <div className="text-sm text-brand-muted">No students enrolled yet.</div>
          ) : (
            <div className="bg-white rounded-xl border border-brand-border overflow-hidden">
              {sortedStudents.map((student, i) => {
                const style = getMasteryStyle(student.avgMastery);
                return (
                  <Link
                    key={student.id}
                    to={`/teacher/students/${student.id}/profile`}
                    className={`flex items-center justify-between px-4 py-3 hover:bg-brand-border-soft/50 transition-colors ${i > 0 ? "border-t border-brand-border" : ""}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${style.dotClass}`} />
                      <span className="text-sm font-medium text-brand-ink">
                        {student.name}
                      </span>
                    </div>
                    <span className={`text-sm font-semibold ${style.textClass}`}>
                      {scoreToPercent(student.avgMastery)}
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        <div>
          <h2 className="font-display font-semibold text-lg text-brand-ink mb-3">
            Recent Assessments
          </h2>
          {assessmentsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : recentAssessments.length === 0 ? (
            <div className="text-sm text-brand-muted">
              No assessments created yet.
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-brand-border overflow-hidden">
              {recentAssessments.map((assessment, i) => (
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
      </div>
    </div>
  );
}
