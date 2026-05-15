import { Link, useParams } from "react-router-dom";
import { useClass } from "../../hooks/useClass";
import { ClassLessonPlansContent } from "../../components/lesson-plans/ClassLessonPlansContent";

export function AllLessonPlansPage() {
  const { classId } = useParams<{ classId: string }>();
  const { data: currentClass } = useClass(classId);

  if (!classId) {
    return (
      <div className="p-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
          Lesson Plans
        </h1>
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-4" role="img" aria-label="lesson plans">
            📋
          </div>
          <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
            Select a class to view its lesson plans.
          </h3>
          <p className="text-sm text-brand-muted max-w-sm mx-auto mb-6">
            Lesson plans are generated on-demand — pick a class and choose which
            subtopics to focus on.
          </p>
          <Link
            to="/teacher/classes"
            className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
          >
            Go to Classes →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <nav
        className="flex items-center gap-2 text-sm text-brand-muted"
        aria-label="Breadcrumb"
      >
        <Link
          to="/teacher/classes"
          className="hover:text-brand-ink transition-colors"
        >
          Classes
        </Link>
        <span aria-hidden="true">/</span>
        <Link
          to={`/teacher/classes/${classId}`}
          className="hover:text-brand-ink transition-colors"
        >
          {currentClass?.name ?? "Class"}
        </Link>
        <span aria-hidden="true">/</span>
        <span className="text-brand-ink font-medium">Lesson Plans</span>
      </nav>

      <ClassLessonPlansContent classId={classId} />
    </div>
  );
}
