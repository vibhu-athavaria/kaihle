import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, BookOpen, FileText, Play } from "lucide-react";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useClassTopics } from "../../hooks/useClassTopics";

export function ClassTopicsPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();
  const { data: topics, isPending, isError } = useClassTopics(classId!);

  const classInfo = layout.sidebarClasses.find((c) => c.id === classId);

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/student/dashboard");
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
            onClick={handleBack}
            className="flex items-center gap-2 text-brand-muted hover:text-brand-ink transition-colors"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
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
                    <BookOpen
                      className="w-5 h-5 text-brand-primary"
                      aria-hidden="true"
                    />
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
            <BookOpen
              className="w-12 h-12 text-brand-muted mx-auto mb-4"
              aria-hidden="true"
            />
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
              <FileText
                className="w-5 h-5 text-brand-muted"
                aria-hidden="true"
              />
              <span className="font-sans text-sm text-brand-body">
                Lesson plans and materials
              </span>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-xl border border-dashed border-brand-border">
              <Play className="w-5 h-5 text-brand-muted" aria-hidden="true" />
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
