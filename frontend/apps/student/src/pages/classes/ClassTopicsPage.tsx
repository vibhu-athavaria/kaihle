import { useParams, useNavigate } from "react-router-dom";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useClassTopics } from "../../hooks/useClassTopics";

export function ClassTopicsPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();
  const { data: topics, isPending, isError } = useClassTopics(classId!);

  const classInfo = layout.sidebarClasses.find((c) => c.id === classId);

  if (isError) {
    return (
      <StudentLayout
        activeNav="home"
        studentName={layout.studentName}
        gradeName={layout.gradeName}
        curriculumName={layout.curriculumName}
        classes={layout.sidebarClasses}
        onLogout={layout.onLogout}
      >
        <div className="text-center py-16">
          <p className="font-sans text-sm text-brand-body">
            Something went wrong loading class topics. Please refresh the page.
          </p>
        </div>
      </StudentLayout>
    );
  }

  return (
    <StudentLayout
      activeNav="home"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      onLogout={layout.onLogout}
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-brand-muted hover:text-brand-ink transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            Back
          </button>
        </div>

        <div className="bg-white rounded-card border border-brand-border p-6">
          <h1 className="font-display font-bold text-2xl text-brand-ink mb-2">
            {classInfo?.name || classInfo?.subjectName || "Class"}
          </h1>
          <p className="font-sans text-sm text-brand-body">
            {classInfo?.teacherName} · {classInfo?.subjectName}
          </p>
        </div>

        {isPending ? (
          <div className="space-y-3">
            <div className="h-20 bg-brand-border rounded-xl animate-pulse" />
            <div className="h-20 bg-brand-border rounded-xl animate-pulse" />
            <div className="h-20 bg-brand-border rounded-xl animate-pulse" />
          </div>
        ) : topics && topics.length > 0 ? (
          <div className="space-y-3">
            <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted">
              Topics
            </h2>
            {topics.map((topic) => (
              <button
                key={topic.id}
                onClick={() =>
                  navigate(`/student/classes/${classId}/topics/${topic.id}`)
                }
                className="w-full text-left bg-white rounded-card border border-brand-border p-4 shadow-card transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
                    <svg
                      className="w-5 h-5 text-brand-primary"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                      />
                    </svg>
                  </div>
                  <div className="text-left">
                    <h3 className="font-sans font-semibold text-base text-brand-ink">
                      {topic.name}
                    </h3>
                    <p className="font-sans text-sm text-brand-body">
                      {topic.description || "No description"}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-card border border-brand-border p-8 text-center">
            <svg
              className="w-12 h-12 text-brand-muted mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
            <h3 className="font-display font-bold text-lg text-brand-ink mb-2">
              No topics available
            </h3>
            <p className="font-sans text-sm text-brand-body">
              Your teacher will add topics to this class soon.
            </p>
          </div>
        )}

        {/* Resources Section */}
        <div className="bg-white rounded-card border border-brand-border p-6">
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-4">
            Class Resources
          </h2>
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-3 rounded-xl border border-dashed border-brand-border">
              <svg
                className="w-5 h-5 text-brand-muted"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span className="font-sans text-sm text-brand-body">
                Lesson plans and materials
              </span>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-xl border border-dashed border-brand-border">
              <svg
                className="w-5 h-5 text-brand-muted"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="font-sans text-sm text-brand-body">
                Video lessons
              </span>
            </div>
          </div>
        </div>
      </div>
    </StudentLayout>
  );
}
