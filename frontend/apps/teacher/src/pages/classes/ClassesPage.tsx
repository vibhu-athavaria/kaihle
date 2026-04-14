import { useAuth } from "@kaihle/auth";
import { useTeacherClasses } from "../../hooks/useTeacherClasses";
import { ClassCard, ClassCardSkeleton } from "../dashboard/ClassCard";

export function ClassesPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? null;
  const { data, isLoading } = useTeacherClasses(schoolId, true);

  return (
    <div className="p-6">
      <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
        Classes
      </h1>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <ClassCardSkeleton key={i} />
          ))}
        </div>
      ) : !data || data.length === 0 ? (
        <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
          <div className="text-4xl mb-3" role="img" aria-label="books">
            📚
          </div>
          <h3 className="font-display font-semibold text-brand-ink mb-1">
            No classes yet
          </h3>
          <p className="text-sm text-brand-muted">
            Classes will appear here once your school admin creates them.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.map((cls) => (
            <ClassCard
              key={cls.id}
              classId={cls.id}
              className={cls.name}
              subjectName={cls.subjectName}
              gradeName={cls.gradeName}
              studentCount={cls.studentCount}
              avgMastery={cls.avgMastery}
            />
          ))}
        </div>
      )}
    </div>
  );
}
