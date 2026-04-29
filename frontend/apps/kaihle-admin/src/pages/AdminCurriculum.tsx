/**
 * AdminCurriculum page - Kaihle Admin curriculum management.
 *
 * Features:
 * - Left panel: Tree view of Curriculum → Grade → Subject hierarchy
 * - Right panel: Detail view showing topics and subtopics for selected item
 * - Full CRUD operations via modals
 */

import { useState } from "react";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  Plus,
  ChevronRight,
  ChevronDown,
  Edit2,
  Trash2,
  BookOpen,
} from "lucide-react";
import {
  useCurricula,
  useGrades,
  useSubjects,
  useCreateCurriculum,
  useUpdateCurriculum,
  useCreateGrade,
  useUpdateGrade,
  useCreateSubject,
  useUpdateSubject,
  useLinkSubject,
  useUnlinkSubject,
  useAddTopic,
  useUpdateCurriculumTopic,
  useCreateSubtopic,
  useUpdateSubtopic,
  Curriculum,
  Grade,
  Subject,
  Topic,
  Subtopic,
} from "../hooks/useCurriculum";
import {
  CreateCurriculumModal,
  EditCurriculumModal,
  CreateGradeModal,
  EditGradeModal,
  CreateSubjectModal,
  EditSubjectModal,
  LinkSubjectModal,
  AddTopicModal,
  EditTopicModal,
  AddSubtopicModal,
  EditSubtopicModal,
} from "../components/curriculum";

type TreeNodeType = "curriculum" | "grade" | "subject" | "topic" | null;

interface TreeNode {
  id: string;
  type: TreeNodeType;
  name: string;
  data: Curriculum | Grade | Subject | Topic | null;
}

function TreeItem({
  node,
  isExpanded,
  isSelected,
  onToggle,
  onSelect,
  onEdit,
  onDelete,
  onAddChild,
  level = 0,
}: {
  node: TreeNode;
  isExpanded: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onSelect: () => void;
  onEdit: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
  onAddChild?: (e: React.MouseEvent) => void;
  level?: number;
}) {
  const hasChildren = node.type === "curriculum" || node.type === "grade";
  const paddingLeft = level * 16 + 12;

  return (
    <div
      className={`group flex items-center gap-1 py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors ${
        isSelected ? "bg-brand-primary/10 hover:bg-brand-primary/15" : ""
      }`}
      style={{ paddingLeft }}
      onClick={onSelect}
    >
      {hasChildren ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          className="p-0.5 rounded hover:bg-gray-200"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </button>
      ) : (
        <span className="w-5" />
      )}

      <span className="flex-1 text-sm font-medium text-gray-900 truncate">
        {node.name}
      </span>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onAddChild && (
          <button
            onClick={onAddChild}
            className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
            title="Add child"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          onClick={onEdit}
          className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
          title="Edit"
        >
          <Edit2 className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-red-600"
          title="Delete"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

export function AdminCurriculum() {
  const { logout } = useAuth();

  // Tree selection state
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Modal states
  const [modalState, setModalState] = useState<{
    type: string | null;
    data?: unknown;
  }>({ type: null });

  // API hooks
  const { data: curricula = [] } = useCurricula();
  const { data: grades = [] } = useGrades();
  const { data: subjects = [] } = useSubjects();

  // Mutations
  const createCurriculum = useCreateCurriculum();
  const updateCurriculum = useUpdateCurriculum();
  const createGrade = useCreateGrade();
  const updateGrade = useUpdateGrade();
  const createSubject = useCreateSubject();
  const updateSubject = useUpdateSubject();
  const linkSubject = useLinkSubject();
  const unlinkSubject = useUnlinkSubject();
  const addTopic = useAddTopic();
  const updateTopic = useUpdateCurriculumTopic();
  const createSubtopic = useCreateSubtopic();
  const updateSubtopic = useUpdateSubtopic();

  // Toggle expand/collapse
  const toggleNode = (id: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedNodes(newExpanded);
  };

  // Get subjects for a curriculum (TODO: filter by curriculum once endpoint exists)
  const getCurriculumSubjects = (_curriculumId: string) => subjects;

  // Close modal helper
  const closeModal = () => setModalState({ type: null });

  // Modal open handlers
  const openCreateCurriculum = () =>
    setModalState({ type: "createCurriculum" });
  const openEditCurriculum = (curriculum: Curriculum) =>
    setModalState({ type: "editCurriculum", data: curriculum });
  const openCreateGrade = () => setModalState({ type: "createGrade" });
  const openEditGrade = (grade: Grade) =>
    setModalState({ type: "editGrade", data: grade });
  const openCreateSubject = () => setModalState({ type: "createSubject" });
  const openEditSubject = (subject: Subject) =>
    setModalState({ type: "editSubject", data: subject });
  const openLinkSubject = (curriculumId: string) =>
    setModalState({ type: "linkSubject", data: { curriculumId } });
  const openAddTopic = (
    curriculumId: string,
    gradeId: string,
    subjectId: string,
  ) =>
    setModalState({
      type: "addTopic",
      data: { curriculumId, gradeId, subjectId },
    });
  const openEditTopic = (topic: Topic) =>
    setModalState({ type: "editTopic", data: topic });
  const openAddSubtopic = (ctId: string, topicName: string) =>
    setModalState({ type: "addSubtopic", data: { ctId, topicName } });
  const openEditSubtopic = (subtopic: Subtopic, topicName: string) =>
    setModalState({ type: "editSubtopic", data: { subtopic, topicName } });

  // Suppress unused-variable lint — these openers are wired to topic/subtopic
  // detail panel actions that are not yet rendered (detail panel is a stub).
  void openEditTopic;
  void openAddSubtopic;
  void openEditSubtopic;

  return (
    <AdminLayout pageTitle="Curriculum" onLogout={logout}>
      <div className="flex h-[calc(100vh-140px)] gap-4">
        {/* Left Panel - Tree View */}
        <div className="w-80 bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
          <div className="p-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Hierarchy</h2>
            <button
              onClick={openCreateCurriculum}
              className="p-1.5 rounded-lg bg-brand-primary text-white hover:bg-brand-primary/90"
              title="Create curriculum"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {/* Curricula */}
            {curricula.map((curriculum) => (
              <div key={curriculum.id}>
                <TreeItem
                  node={{
                    id: curriculum.id,
                    type: "curriculum",
                    name: curriculum.name,
                    data: curriculum,
                  }}
                  isExpanded={expandedNodes.has(curriculum.id)}
                  isSelected={selectedNode?.id === curriculum.id}
                  onToggle={() => toggleNode(curriculum.id)}
                  onSelect={() =>
                    setSelectedNode({
                      id: curriculum.id,
                      type: "curriculum",
                      name: curriculum.name,
                      data: curriculum,
                    })
                  }
                  onEdit={(e) => {
                    e.stopPropagation();
                    openEditCurriculum(curriculum);
                  }}
                  onDelete={(e) => {
                    e.stopPropagation();
                    // TODO: Implement delete
                  }}
                  onAddChild={(e) => {
                    e.stopPropagation();
                    openLinkSubject(curriculum.id);
                  }}
                />

                {/* Grades under curriculum */}
                {expandedNodes.has(curriculum.id) &&
                  grades.map((grade) => (
                    <div key={`${curriculum.id}-${grade.id}`}>
                      <TreeItem
                        node={{
                          id: `${curriculum.id}-${grade.id}`,
                          type: "grade",
                          name: grade.name,
                          data: grade,
                        }}
                        isExpanded={expandedNodes.has(
                          `${curriculum.id}-${grade.id}`,
                        )}
                        isSelected={
                          selectedNode?.id === `${curriculum.id}-${grade.id}`
                        }
                        onToggle={() =>
                          toggleNode(`${curriculum.id}-${grade.id}`)
                        }
                        onSelect={() =>
                          setSelectedNode({
                            id: `${curriculum.id}-${grade.id}`,
                            type: "grade",
                            name: grade.name,
                            data: grade,
                          })
                        }
                        onEdit={(e) => {
                          e.stopPropagation();
                          openEditGrade(grade);
                        }}
                        onDelete={(e) => {
                          e.stopPropagation();
                          // TODO: Implement delete
                        }}
                        level={1}
                      />

                      {/* Subjects under grade/curriculum */}
                      {expandedNodes.has(`${curriculum.id}-${grade.id}`) &&
                        getCurriculumSubjects(curriculum.id).map((subject) => (
                          <TreeItem
                            key={`${curriculum.id}-${grade.id}-${subject.id}`}
                            node={{
                              id: `${curriculum.id}-${grade.id}-${subject.id}`,
                              type: "subject",
                              name: subject.name,
                              data: subject,
                            }}
                            isExpanded={false}
                            isSelected={
                              selectedNode?.id ===
                              `${curriculum.id}-${grade.id}-${subject.id}`
                            }
                            onToggle={() => {}}
                            onSelect={() =>
                              setSelectedNode({
                                id: `${curriculum.id}-${grade.id}-${subject.id}`,
                                type: "subject",
                                name: subject.name,
                                data: subject,
                              })
                            }
                            onEdit={(e) => {
                              e.stopPropagation();
                              openEditSubject(subject);
                            }}
                            onDelete={(e) => {
                              e.stopPropagation();
                              unlinkSubject.mutate({
                                curriculumId: curriculum.id,
                                subjectId: subject.id,
                              });
                            }}
                            onAddChild={(e) => {
                              e.stopPropagation();
                              openAddTopic(curriculum.id, grade.id, subject.id);
                            }}
                            level={2}
                          />
                        ))}
                    </div>
                  ))}
              </div>
            ))}
          </div>

          {/* Quick actions */}
          <div className="p-3 border-t border-gray-200 space-y-2">
            <button
              onClick={openCreateGrade}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create grade
            </button>
            <button
              onClick={openCreateSubject}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create subject
            </button>
          </div>
        </div>

        {/* Right Panel - Detail View */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
          {selectedNode ? (
            <>
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      {selectedNode.name}
                    </h2>
                    <p className="text-sm text-gray-500 capitalize">
                      {selectedNode.type}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedNode.type === "subject" && (
                      <button
                        onClick={() => {
                          const subject = selectedNode.data as Subject;
                          // Find parent curriculum and grade from selection
                          openAddTopic(
                            "curriculum-id", // Would need to track this properly
                            "grade-id",
                            subject.id,
                          );
                        }}
                        className="flex items-center gap-2 px-3 py-2 bg-brand-primary text-white rounded-lg text-sm font-medium hover:bg-brand-primary/90"
                      >
                        <Plus className="w-4 h-4" />
                        Add topic
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex-1 p-4 overflow-y-auto">
                <p className="text-gray-500 text-center py-8">
                  Select a subject to view topics and subtopics
                </p>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">Select an item to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <CreateCurriculumModal
        isOpen={modalState.type === "createCurriculum"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await createCurriculum.mutateAsync(data);
          closeModal();
        }}
        isSubmitting={createCurriculum.isPending}
      />

      <EditCurriculumModal
        curriculum={
          modalState.type === "editCurriculum"
            ? (modalState.data as Curriculum)
            : null
        }
        isOpen={modalState.type === "editCurriculum"}
        onClose={closeModal}
        onSubmit={async ({ id, ...fields }) => {
          await updateCurriculum.mutateAsync({ id, data: fields });
          closeModal();
        }}
        isSubmitting={updateCurriculum.isPending}
      />

      <CreateGradeModal
        isOpen={modalState.type === "createGrade"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await createGrade.mutateAsync(data);
          closeModal();
        }}
        isSubmitting={createGrade.isPending}
      />

      <EditGradeModal
        grade={
          modalState.type === "editGrade" ? (modalState.data as Grade) : null
        }
        isOpen={modalState.type === "editGrade"}
        onClose={closeModal}
        onSubmit={async ({ id, ...fields }) => {
          await updateGrade.mutateAsync({ id, data: fields });
          closeModal();
        }}
        isSubmitting={updateGrade.isPending}
      />

      <CreateSubjectModal
        isOpen={modalState.type === "createSubject"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await createSubject.mutateAsync(data);
          closeModal();
        }}
        isSubmitting={createSubject.isPending}
      />

      <EditSubjectModal
        subject={
          modalState.type === "editSubject"
            ? (modalState.data as Subject)
            : null
        }
        isOpen={modalState.type === "editSubject"}
        onClose={closeModal}
        onSubmit={async ({ id, ...fields }) => {
          await updateSubject.mutateAsync({ id, data: fields });
          closeModal();
        }}
        isSubmitting={updateSubject.isPending}
      />

      <LinkSubjectModal
        curriculumId={
          modalState.type === "linkSubject"
            ? (modalState.data as { curriculumId: string }).curriculumId
            : null
        }
        availableSubjects={subjects}
        isOpen={modalState.type === "linkSubject"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await linkSubject.mutateAsync({
            curriculumId: data.curriculumId,
            data: {
              subject_id: data.subjectId,
              is_core: data.isCore,
              sort_order: data.sortOrder,
            },
          });
          closeModal();
        }}
        isSubmitting={linkSubject.isPending}
      />

      <AddTopicModal
        curriculumId={
          modalState.type === "addTopic"
            ? (modalState.data as { curriculumId: string }).curriculumId
            : null
        }
        gradeId={
          modalState.type === "addTopic"
            ? (modalState.data as { gradeId: string }).gradeId
            : null
        }
        subjectId={
          modalState.type === "addTopic"
            ? (modalState.data as { subjectId: string }).subjectId
            : null
        }
        availableTopics={[]}
        isOpen={modalState.type === "addTopic"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await addTopic.mutateAsync({
            curriculumId: data.curriculumId,
            gradeId: data.gradeId,
            subjectId: data.subjectId,
            data: {
              topic_id: data.topicId,
              topic_data: data.topicData,
              standard_code: data.standardCode,
              sequence_order: data.sequenceOrder,
              learning_objectives: data.learningObjectives,
              recommended_weeks: data.recommendedWeeks,
              is_required: data.isRequired,
            },
          });
          closeModal();
        }}
        isSubmitting={addTopic.isPending}
      />

      <EditTopicModal
        topic={
          modalState.type === "editTopic" ? (modalState.data as Topic) : null
        }
        isOpen={modalState.type === "editTopic"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await updateTopic.mutateAsync({
            ctId: data.ctId,
            data: {
              standard_code: data.standardCode,
              sequence_order: data.sequenceOrder,
              learning_objectives: data.learningObjectives,
              recommended_weeks: data.recommendedWeeks,
              is_required: data.isRequired,
              is_active: data.isActive,
            },
          });
          closeModal();
        }}
        isSubmitting={updateTopic.isPending}
      />

      <AddSubtopicModal
        curriculumTopicId={
          modalState.type === "addSubtopic"
            ? (modalState.data as { ctId: string }).ctId
            : null
        }
        topicName={
          modalState.type === "addSubtopic"
            ? (modalState.data as { topicName: string }).topicName
            : ""
        }
        isOpen={modalState.type === "addSubtopic"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await createSubtopic.mutateAsync({
            ctId: data.ctId,
            data: {
              name: data.name,
              learning_objective: data.learningObjective,
              canonical_code: data.canonicalCode,
              description: data.description,
              keywords: data.keywords,
              bloom_taxonomy_level: data.bloomTaxonomyLevel,
              difficulty_level: data.difficultyLevel,
              estimated_minutes: data.estimatedMinutes,
              sequence_order: data.sequenceOrder,
            },
          });
          closeModal();
        }}
        isSubmitting={createSubtopic.isPending}
      />

      <EditSubtopicModal
        subtopic={
          modalState.type === "editSubtopic"
            ? (modalState.data as { subtopic: Subtopic; topicName: string })
                .subtopic
            : null
        }
        topicName={
          modalState.type === "editSubtopic"
            ? (modalState.data as { subtopic: Subtopic; topicName: string })
                .topicName
            : ""
        }
        isOpen={modalState.type === "editSubtopic"}
        onClose={closeModal}
        onSubmit={async (data) => {
          await updateSubtopic.mutateAsync({
            id: (modalState.data as { subtopic: Subtopic; topicName: string })
              .subtopic.id,
            data,
          });
          closeModal();
        }}
        isSubmitting={updateSubtopic.isPending}
      />
    </AdminLayout>
  );
}
