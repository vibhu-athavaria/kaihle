import { useState, useMemo } from "react";
import {
  useTeacherStudents,
  TeacherStudent,
} from "../hooks/useTeacherStudents";
import { StudentListTable } from "../components/students/StudentListTable";
import { useAuth } from "@kaihle/auth";

export function MyStudentsPage() {
  const { user } = useAuth();
  const schoolId = user?.school_id || null;
  const { data: teacherStudents, isLoading: studentsLoading } =
    useTeacherStudents(schoolId);

  const [filterClassId, setFilterClassId] = useState<string | null>(null);

  const allClassIds = useMemo(() => {
    if (!teacherStudents) return [];
    return [...new Set(teacherStudents.flatMap((s) => s.class_ids))];
  }, [teacherStudents]);

  const classIdNameMap = useMemo(() => {
    if (!teacherStudents) return new Map<string, string>();
    const map = new Map<string, string>();
    for (const student of teacherStudents) {
      for (let i = 0; i < student.class_ids.length; i++) {
        map.set(student.class_ids[i], student.class_names[i]);
      }
    }
    return map;
  }, [teacherStudents]);

  const allStudents = useMemo(() => {
    if (!teacherStudents) return [];
    return teacherStudents.map((s: TeacherStudent) => ({
      id: s.id,
      name: `${s.first_name} ${s.last_name}`.trim(),
      // Username-based students have no email — show the username instead.
      email: s.email ?? s.username ?? "",
      gradeName: s.grade_name ?? null,
      classIds: s.class_ids,
      classNames: s.class_names,
    }));
  }, [teacherStudents]);

  const filteredStudents = useMemo(() => {
    if (filterClassId === null) return allStudents;
    return allStudents.filter((s) => s.classIds?.includes(filterClassId));
  }, [allStudents, filterClassId]);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Students
        </h1>
        <p className="text-sm text-brand-muted">
          View student roster across all your classes
        </p>
      </div>

      {allClassIds.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFilterClassId(null)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filterClassId === null
                ? "bg-brand-gold text-white"
                : "bg-white border border-brand-border text-brand-muted hover:text-brand-ink"
            }`}
          >
            All ({allStudents.length})
          </button>
          {allClassIds.map((classId) => (
            <button
              key={classId}
              type="button"
              onClick={() => setFilterClassId(classId)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                filterClassId === classId
                  ? "bg-brand-gold text-white"
                  : "bg-white border border-brand-border text-brand-muted hover:text-brand-ink"
              }`}
            >
              {classIdNameMap.get(classId)}
            </button>
          ))}
        </div>
      )}

      <StudentListTable
        students={filteredStudents}
        isLoading={studentsLoading}
      />
    </div>
  );
}
