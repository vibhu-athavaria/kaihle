import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, BookOpen, FileText, Play, CheckCircle } from "lucide-react";
import { toast } from "@kaihle/ui";
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

  const handleComingSoon = (feature: string) => {
    toast.info(`${feature} is coming soon!`);
  };

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(`/student/classes/${classId}/topics`);
    }
  };

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
            onClick={handleBack}
            className="flex items-center gap-1 text-brand-muted hover:text-brand-ink transition-colors"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
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
                  <BookOpen
                    className="w-7 h-7 text-brand-primary"
                    aria-hidden="true"
                  />
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
                    <FileText
                      className="w-5 h-5 text-brand-primary"
                      aria-hidden="true"
                    />
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
                <button
                  onClick={() => handleComingSoon("Lesson Plan")}
                  className="w-full font-sans font-semibold text-sm text-brand-primary hover:text-brand-dark transition-colors text-left"
                >
                  View Lesson Plan
                </button>
              </div>

              {/* Video Lesson */}
              <div className="bg-white rounded-card border border-brand-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center">
                    <Play
                      className="w-5 h-5 text-brand-primary"
                      aria-hidden="true"
                    />
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
                <button
                  onClick={() => handleComingSoon("Video Lesson")}
                  className="w-full font-sans font-semibold text-sm text-brand-primary hover:text-brand-dark transition-colors text-left"
                >
                  Watch Now
                </button>
              </div>
            </div>

            {/* Practice Section */}
            <div className="bg-gradient-to-br from-brand-primary/5 to-brand-primary/10 rounded-card border border-brand-primary/20 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-brand-primary flex items-center justify-center">
                  <CheckCircle
                    className="w-5 h-5 text-white"
                    aria-hidden="true"
                  />
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
            <BookOpen
              className="w-12 h-12 text-brand-muted mx-auto mb-4"
              aria-hidden="true"
            />
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
