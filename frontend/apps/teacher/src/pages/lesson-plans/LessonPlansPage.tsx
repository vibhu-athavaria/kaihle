import { Link, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

export function LessonPlansPage() {
  const { classId: _classId } = useParams<{ classId: string }>();

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          to="/teacher/dashboard"
          className="inline-flex items-center gap-1 text-sm text-brand-muted hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 rounded"
        >
          <ChevronLeft className="w-4 h-4" aria-hidden="true" />
          Back to dashboard
        </Link>
      </div>

      <div>
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Lesson Plans
        </h1>
        <p className="text-sm text-brand-muted">
          Lesson plans for this class will appear here soon.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
        <span className="text-4xl mb-3" role="img" aria-label="construction">
          🚧
        </span>
        <h3 className="font-display font-semibold text-brand-ink mb-1">
          Coming Soon
        </h3>
        <p className="text-sm text-brand-muted">
          Lesson plan generation is currently in development. Check back later!
        </p>
      </div>
    </div>
  );
}
