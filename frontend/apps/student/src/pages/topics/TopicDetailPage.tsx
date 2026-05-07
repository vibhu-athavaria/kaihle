import { useParams, useNavigate } from "react-router-dom";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useTopicDetail } from "../../hooks/useTopicDetail";

export function TopicDetailPage() {
  const { classId, topicId } = useParams<{
    classId: string;
    topicId: string;
  }>();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();
  const {
    data: topic,
    isPending,
    isError,
  } = useTopicDetail(classId!, topicId!);

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
            Something went wrong loading the topic. Please refresh the page.
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
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-brand-muted hover:text-brand-ink transition-colors"
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
          <span className="text-brand-muted">/</span>
          <button
            onClick={() => navigate(`/student/classes/${classId}/topics`)}
            className="text-brand-muted hover:text-brand-ink transition-colors"
          >
            {classInfo?.name || classInfo?.subjectName || "Class"}
          </button>
          <span className="text-brand-muted">/</span>
          <span className="text-brand-ink font-medium">
            {isPending ? "Loading..." : topic?.name}
          </span>
        </div>

        {isPending ? (
          <div className="space-y-4">
            <div className="h-8 w-1/3 bg-brand-border rounded-full animate-pulse" />
            <div className="h-4 w-2/3 bg-brand-border rounded animate-pulse" />
            <div className="h-32 bg-brand-border rounded-xl animate-pulse" />
          </div>
        ) : topic ? (
          <>
            {/* Topic Header */}
            <div className="bg-white rounded-card border border-brand-border p-6">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-2xl bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
                  <svg
                    className="w-7 h-7 text-brand-primary"
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
                <div className="flex-1">
                  <h1 className="font-display font-bold text-2xl text-brand-ink mb-2">
                    {topic.name}
                  </h1>
                  <p className="font-sans text-sm text-brand-body">
                    {topic.description || "No description available"}
                  </p>
                </div>
              </div>
            </div>

            {/* Content Sections */}
            <div className="grid md:grid-cols-2 gap-4">
              {/* Lesson Plan */}
              <div className="bg-white rounded-card border border-brand-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center">
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
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h2 className="font-sans font-semibold text-base text-brand-ink">
                      Lesson Plan
                    </h2>
                    <p className="font-sans text-xs text-brand-muted">
                      Teacher's guide and objectives
                    </p>
                  </div>
                </div>
                <p className="font-sans text-sm text-brand-body mb-4">
                  This lesson covers the fundamental concepts. Work through the
                  materials at your own pace.
                </p>
                <button className="w-full font-sans font-semibold text-sm text-brand-primary hover:text-brand-dark transition-colors text-left">
                  View Lesson Plan
                </button>
              </div>

              {/* Video Lesson */}
              <div className="bg-white rounded-card border border-brand-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center">
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
                        d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h2 className="font-sans font-semibold text-base text-brand-ink">
                      Video Lesson
                    </h2>
                    <p className="font-sans text-xs text-brand-muted">
                      Watch and learn
                    </p>
                  </div>
                </div>
                <p className="font-sans text-sm text-brand-body mb-4">
                  A 10-minute video explaining the key concepts with examples.
                </p>
                <button className="w-full font-sans font-semibold text-sm text-brand-primary hover:text-brand-dark transition-colors text-left">
                  Watch Now
                </button>
              </div>
            </div>

            {/* Practice Section */}
            <div className="bg-gradient-to-br from-brand-primary/5 to-brand-primary/10 rounded-card border border-brand-primary/20 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-brand-primary flex items-center justify-center">
                  <svg
                    className="w-5 h-5 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
                <div>
                  <h2 className="font-sans font-semibold text-base text-brand-ink">
                    Check Your Understanding
                  </h2>
                  <p className="font-sans text-xs text-brand-muted">
                    Quick practice questions
                  </p>
                </div>
              </div>
              <p className="font-sans text-sm text-brand-body mb-4">
                Test your knowledge with these quick questions before moving on.
              </p>
              <button className="font-sans font-semibold text-sm text-brand-primary hover:text-brand-dark transition-colors">
                Start Practice
              </button>
            </div>
          </>
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
              Topic not found
            </h3>
            <p className="font-sans text-sm text-brand-body">
              This topic doesn't exist or has been removed.
            </p>
          </div>
        )}
      </div>
    </StudentLayout>
  );
}
