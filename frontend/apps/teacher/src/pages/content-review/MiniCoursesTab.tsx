import { Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { useTeacherClasses } from "../../hooks/useTeacherClasses";
import { useClassTopics } from "../../hooks/useClassTopics";
import { EmptyState, SkeletonCard, Badge } from "@kaihle/ui";
import { BookOpen, Sparkles, AlertCircle } from "lucide-react";

function statusBadge(status: string) {
  switch (status) {
    case "ready":
      return <Badge variant="success">Ready</Badge>;
    case "generating":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-brand-gold bg-[#fffbeb] border border-brand-gold/30 animate-pulse">
          <Sparkles className="w-3 h-3" aria-hidden="true" />
          Generating
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-red-600 bg-red-50 border border-red-200">
          <AlertCircle className="w-3 h-3" aria-hidden="true" />
          Failed
        </span>
      );
    default:
      return null;
  }
}

function ClassMiniCourses({
  classId,
  className,
  gradeName,
}: {
  classId: string;
  className: string;
  gradeName: string;
}) {
  const { data: topics = [], isLoading } = useClassTopics(classId);
  const coursesWithContent = topics.filter(
    (t) => t.mini_course_status !== "none",
  );

  if (isLoading) return <SkeletonCard />;
  if (coursesWithContent.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-bold uppercase tracking-widest text-brand-muted">
        {className} · {gradeName}
      </p>
      {coursesWithContent.map((topic) => (
        <div
          key={topic.topic_id}
          className="bg-white rounded-xl border border-brand-border p-4 flex items-center justify-between gap-4"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              {statusBadge(topic.mini_course_status)}
            </div>
            <h3 className="font-display font-semibold text-brand-ink text-sm truncate">
              {topic.topic_name}
            </h3>
            <p className="text-xs text-brand-muted mt-0.5">
              {topic.subtopic_count} subtopic
              {topic.subtopic_count !== 1 ? "s" : ""}
              {" · "}
              {className}
              {" · "}
              {gradeName}
            </p>
          </div>

          {topic.mini_course_status === "ready" && (
            <Link
              to={`/teacher/content-review/mini-courses/${topic.topic_id}?classId=${classId}`}
              className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border border-brand-primary text-brand-primary hover:bg-brand-primary hover:text-white transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
              View →
            </Link>
          )}
        </div>
      ))}
    </div>
  );
}

export function MiniCoursesTab() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;

  const { data: classes = [], isLoading: classesLoading } = useTeacherClasses(
    schoolId,
    false,
  );

  if (classesLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (classes.length === 0) {
    return (
      <EmptyState
        emoji="📚"
        title="No mini-courses yet"
        description="Go to a class topic list and click 'Generate Mini-Course' to create personalised content for your students."
      />
    );
  }

  return (
    <div className="space-y-6">
      {classes.map((cls) => (
        <ClassMiniCourses
          key={cls.id}
          classId={cls.id}
          className={cls.name}
          gradeName={cls.gradeName}
        />
      ))}
    </div>
  );
}
