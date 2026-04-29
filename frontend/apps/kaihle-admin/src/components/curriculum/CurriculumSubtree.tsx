import { ChevronRight, ChevronDown, Edit2, Trash2, Plus } from "lucide-react";
import {
  useGrades,
  useSubjects,
  Grade,
  Subject,
} from "../../hooks/useCurriculum";

interface CurriculumSubtreeProps {
  curriculumId: string;
  expandedNodes: Set<string>;
  selectedNodeId: string | null;
  onToggleNode: (id: string) => void;
  onSelectNode: (
    id: string,
    type: "grade" | "subject",
    data: Grade | Subject,
  ) => void;
  onEditGrade: (grade: Grade) => void;
  onEditSubject: (subject: Subject) => void;
  onLinkSubject: (curriculumId: string) => void;
  onOpenAddTopic: (
    curriculumId: string,
    gradeId: string,
    subjectId: string,
  ) => void;
  onUnlinkSubject: (curriculumId: string, subjectId: string) => void;
}

export function CurriculumSubtree({
  curriculumId,
  expandedNodes,
  selectedNodeId,
  onToggleNode,
  onSelectNode,
  onEditGrade,
  onEditSubject,
  onLinkSubject,
  onOpenAddTopic,
  onUnlinkSubject,
}: CurriculumSubtreeProps) {
  const { data: grades = [], isLoading: gradesLoading } =
    useGrades(curriculumId);
  const { data: subjects = [] } = useSubjects(curriculumId);

  if (gradesLoading) {
    return (
      <div className="animate-pulse space-y-1 px-4 py-1">
        <div className="h-4 bg-gray-100 rounded w-3/4" />
        <div className="h-4 bg-gray-100 rounded w-2/3" />
      </div>
    );
  }

  return (
    <>
      {grades.map((grade) => {
        const gradeNodeId = `${curriculumId}-${grade.id}`;
        const isGradeExpanded = expandedNodes.has(gradeNodeId);
        const isGradeSelected = selectedNodeId === gradeNodeId;

        return (
          <div key={gradeNodeId}>
            {/* Grade row */}
            <div
              className={`group flex items-center gap-1 py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                isGradeSelected
                  ? "bg-brand-primary/10 hover:bg-brand-primary/15"
                  : ""
              }`}
              style={{ paddingLeft: 28 }}
              onClick={() => onSelectNode(gradeNodeId, "grade", grade)}
            >
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleNode(gradeNodeId);
                }}
                className="p-0.5 rounded hover:bg-gray-200"
              >
                {isGradeExpanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-500" />
                )}
              </button>
              <span className="flex-1 text-sm font-medium text-gray-900 truncate">
                {grade.name}
              </span>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onLinkSubject(curriculumId);
                  }}
                  className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
                  title="Add subject"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onEditGrade(grade);
                  }}
                  className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
                  title="Edit grade"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Subjects under this grade */}
            {isGradeExpanded &&
              subjects.map((subject) => {
                const subjectNodeId = `${curriculumId}-${grade.id}-${subject.id}`;
                const isSubjectSelected = selectedNodeId === subjectNodeId;

                return (
                  <div
                    key={subjectNodeId}
                    className={`group flex items-center gap-1 py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                      isSubjectSelected ? "bg-[#e8f5e9] hover:bg-[#e8f5e9]" : ""
                    }`}
                    style={{ paddingLeft: 44 }}
                    onClick={() =>
                      onSelectNode(subjectNodeId, "subject", subject)
                    }
                  >
                    {isSubjectSelected && (
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0" />
                    )}
                    <span
                      className={`flex-1 text-sm truncate ${
                        isSubjectSelected
                          ? "font-semibold text-brand-primary"
                          : "font-medium text-gray-900"
                      }`}
                    >
                      {subject.name}
                    </span>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenAddTopic(curriculumId, grade.id, subject.id);
                        }}
                        className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
                        title="Add topic"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onEditSubject(subject);
                        }}
                        className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
                        title="Edit subject"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onUnlinkSubject(curriculumId, subject.id);
                        }}
                        className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-red-600"
                        title="Remove subject from curriculum"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
          </div>
        );
      })}
    </>
  );
}
