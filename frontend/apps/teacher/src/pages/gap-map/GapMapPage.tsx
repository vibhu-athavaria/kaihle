import { useParams, Link } from "react-router-dom";
import { useClass } from "../../hooks/useClass";
import { ClassGapMapContent } from "../../components/gap-map/ClassGapMapContent";

export function GapMapPage() {
  const { classId } = useParams<{ classId: string }>();
  const { data: currentClass } = useClass(classId);

  if (!classId) return null;

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
        <span className="text-brand-ink font-medium">Gap Map</span>
      </nav>

      <ClassGapMapContent classId={classId} showExport />
    </div>
  );
}
