import { useState } from "react";
import { Plus } from "lucide-react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  useGrades,
  useCurricula,
  useCreateGrade,
  useUpdateGrade,
  Grade,
} from "../hooks/useCurriculum";
import { GradeTable, GradeRow } from "../components/grades/GradeTable";
import { CreateGradeModal, EditGradeModal } from "../components/curriculum";

type StatusFilter = "ALL" | "active" | "inactive";

export function AdminGrades() {
  const { logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [curriculumFilter, setCurriculumFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [currentPage, setCurrentPage] = useState(1);
  const [editingGrade, setEditingGrade] = useState<Grade | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const { data: grades = [], isLoading } = useGrades();
  const { data: curricula = [] } = useCurricula();

  const createGrade = useCreateGrade();
  const updateGrade = useUpdateGrade();

  const curriculumNameById = Object.fromEntries(
    curricula.map((c) => [c.id, c.name]),
  );

  const filteredGrades = grades.filter((g) => {
    const matchesSearch =
      !searchQuery ||
      g.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      g.level.toString().includes(searchQuery);

    const matchesCurriculum =
      curriculumFilter === "ALL" ||
      (g.curriculum_ids ?? []).includes(curriculumFilter);

    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "active" && g.is_active) ||
      (statusFilter === "inactive" && !g.is_active);

    return matchesSearch && matchesCurriculum && matchesStatus;
  });

  const pageSize = 25;
  const totalPages = Math.max(1, Math.ceil(filteredGrades.length / pageSize));
  const pagedGrades = filteredGrades.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  const gradeRows: GradeRow[] = pagedGrades.map((g) => ({
    ...g,
    curriculum_names: (g.curriculum_ids ?? []).map(
      (id) => curriculumNameById[id] ?? id,
    ),
  }));

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setCurrentPage(1);
  };

  const handleCurriculumFilterChange = (value: string) => {
    setCurriculumFilter(value);
    setCurrentPage(1);
  };

  const handleStatusFilterChange = (value: StatusFilter) => {
    setStatusFilter(value);
    setCurrentPage(1);
  };

  return (
    <AdminLayout
      pageTitle="Grades"
      onLogout={logout}
      topNavAction={
        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-primary text-white rounded-full text-sm font-medium font-['Inter'] hover:bg-brand-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" aria-hidden="true" />
          Add grade
        </button>
      }
    >
      <GradeTable
        grades={gradeRows}
        isLoading={isLoading}
        searchQuery={searchQuery}
        curriculumFilter={curriculumFilter}
        statusFilter={statusFilter}
        onSearchChange={handleSearchChange}
        onCurriculumFilterChange={handleCurriculumFilterChange}
        onStatusFilterChange={handleStatusFilterChange}
        onEditClick={setEditingGrade}
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
        curricula={curricula}
      />

      <CreateGradeModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={async (data) => {
          setModalError(null);
          await createGrade.mutateAsync(data);
          setIsCreateOpen(false);
        }}
        isSubmitting={createGrade.isPending}
        error={modalError}
      />

      <EditGradeModal
        grade={editingGrade}
        isOpen={!!editingGrade}
        onClose={() => {
          setEditingGrade(null);
          setModalError(null);
        }}
        onSubmit={async ({ id, ...fields }) => {
          setModalError(null);
          await updateGrade.mutateAsync({ id, data: fields });
          setEditingGrade(null);
        }}
        isSubmitting={updateGrade.isPending}
        error={modalError}
      />
    </AdminLayout>
  );
}
