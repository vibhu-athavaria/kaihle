import { Link } from "react-router-dom";

// M4 stub — lesson plan endpoint not yet implemented.
// Shows empty state UI. Never throws. Will be wired to real data in M4.
export function AllLessonPlansPage() {
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
          Lesson plans are generated every Monday at 6am.
        </h3>
        <p className="text-sm text-brand-muted max-w-sm mx-auto mb-4">
          They&apos;re built around your students&apos; topic gaps —
          personalised to whichever subtopics your class is struggling with that
          week.
        </p>
        <p className="text-sm text-brand-muted max-w-sm mx-auto mb-6">
          Create assessments first to unlock personalised plans.
        </p>
        <Link
          to="/teacher/assessments/new"
          className="text-sm font-semibold text-brand-gold hover:text-brand-gold-dark focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded transition-colors"
        >
          Create an Assessment →
        </Link>
      </div>
    </div>
  );
}
