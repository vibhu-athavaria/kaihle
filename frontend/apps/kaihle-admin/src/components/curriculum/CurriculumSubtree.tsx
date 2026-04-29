import { Edit2, Trash2, Plus } from "lucide-react";
import { useSubjects, Subject } from "../../hooks/useCurriculum";

interface CurriculumSubtreeProps {
  curriculumId: string;
  selectedSubjectId: string | null;
  onSelectSubject: (subject: Subject & { curriculumId: string }) => void;
  onEditSubject: (subject: Subject) => void;
  onAddTopic: (curriculumId: string, subjectId: string) => void;
  onUnlinkSubject: (curriculumId: string, subjectId: string) => void;
}

export function CurriculumSubtree({
  curriculumId,
  selectedSubjectId,
  onSelectSubject,
  onEditSubject,
  onAddTopic,
  onUnlinkSubject,
}: CurriculumSubtreeProps) {
  const { data: subjects = [], isLoading } = useSubjects(curriculumId);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-1 px-4 py-1">
        <div className="h-4 bg-gray-100 rounded w-3/4" />
        <div className="h-4 bg-gray-100 rounded w-2/3" />
      </div>
    );
  }

  return (
    <>
      {subjects.map((subject) => {
        const isSelected = selectedSubjectId === subject.id;

        return (
          <div
            key={subject.id}
            data-selected={isSelected ? "" : undefined}
            className={`group flex items-center gap-1 py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors ${
              isSelected ? "bg-[#e8f5e9] hover:bg-[#e8f5e9]" : ""
            }`}
            style={{ paddingLeft: 28 }}
            onClick={() => onSelectSubject({ ...subject, curriculumId })}
          >
            {isSelected && (
              <span className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0" />
            )}
            <span
              className={`flex-1 text-sm truncate ${
                isSelected
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
                  onAddTopic(curriculumId, subject.id);
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
    </>
  );
}
