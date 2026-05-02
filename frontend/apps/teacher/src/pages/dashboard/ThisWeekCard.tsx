import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";

interface LessonPlan {
  classId: string;
  className: string;
  topics: string[];
}

interface ThisWeekCardProps {
  lessonPlan: LessonPlan | null;
}

export function ThisWeekCard({ lessonPlan }: ThisWeekCardProps) {
  if (!lessonPlan) {
    return (
      <div className="bg-brand-light rounded-xl border border-brand-mid p-4">
        <p className="text-sm text-brand-body">
          No lesson plans yet. Open a class and generate one on demand whenever
          you're ready.
        </p>
      </div>
    );
  }

  const displayTopics = lessonPlan.topics.slice(0, 2).join(", ");

  return (
    <div className="bg-brand-light rounded-xl border border-brand-mid p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <BookOpen className="w-5 h-5 text-brand-primary" />
        <div>
          <div className="text-sm font-semibold text-brand-ink">
            Lesson plan ready · {lessonPlan.className}
          </div>
          <div className="text-xs text-brand-muted mt-0.5">
            Covers: {displayTopics}
          </div>
        </div>
      </div>
      <Link
        to={`/teacher/classes/${lessonPlan.classId}/lesson-plans`}
        className="text-sm font-semibold text-brand-primary hover:text-brand-dark"
      >
        View plan →
      </Link>
    </div>
  );
}
