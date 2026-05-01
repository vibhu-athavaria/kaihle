import { useState } from "react";
import { ChevronRight, ChevronDown, Plus, Edit2 } from "lucide-react";
import {
  useTopics,
  useSubtopics,
  Topic,
  Subtopic,
} from "../../hooks/useCurriculum";

interface SubjectDetailPanelProps {
  subjectId: string;
  subjectName: string;
  curriculumId: string;
  onAddTopic: () => void;
  onEditTopic: (topic: Topic) => void;
  onAddSubtopic: (
    ctId: string,
    topicName: string,
    existingSubtopics: Subtopic[],
  ) => void;
  onEditSubtopic: (subtopic: Subtopic, topicName: string) => void;
}

function SubtopicRow({
  subtopic,
  topicName,
  onEdit,
}: {
  subtopic: Subtopic;
  topicName: string;
  onEdit: () => void;
}) {
  return (
    <div
      className="group flex items-center gap-2 py-2 px-3 hover:bg-gray-50 transition-colors"
      style={{ paddingLeft: 48 }}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-gray-300 flex-shrink-0" />
      <span className="flex-1 text-sm text-gray-700 truncate">
        {subtopic.name}
      </span>
      {subtopic.bloom_taxonomy_level && (
        <span className="text-xs text-gray-400 font-medium capitalize hidden group-hover:inline">
          {subtopic.bloom_taxonomy_level}
        </span>
      )}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onEdit();
        }}
        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700 transition-opacity"
        title={`Edit subtopic of ${topicName}`}
      >
        <Edit2 className="w-3 h-3" />
      </button>
    </div>
  );
}

function TopicRow({
  topic,
  curriculumId,
  isExpanded,
  onToggle,
  onEdit,
  onAddSubtopic,
  onEditSubtopic,
}: {
  topic: Topic;
  curriculumId: string;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onAddSubtopic: (existingSubtopics: Subtopic[]) => void;
  onEditSubtopic: (subtopic: Subtopic) => void;
}) {
  const { data: subtopics = [], isLoading } = useSubtopics(
    topic.topic_id,
    curriculumId,
  );

  return (
    <div>
      <div
        className="group flex items-center gap-2 py-2.5 px-3 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-100"
        onClick={onToggle}
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          className="p-0.5 rounded hover:bg-gray-200 flex-shrink-0"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
        </button>

        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-gray-900">
            {topic.name}
          </span>
          {topic.canonical_code && (
            <span className="ml-2 text-xs text-gray-400 font-mono">
              {topic.canonical_code}
            </span>
          )}
        </div>

        <span className="text-xs text-gray-400 flex-shrink-0">
          {topic.subtopic_count} subtopics
        </span>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAddSubtopic(subtopics);
            }}
            className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
            title="Add subtopic"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
            className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
            title="Edit topic"
          >
            <Edit2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isExpanded && (
        <>
          {isLoading ? (
            <div className="animate-pulse space-y-1 py-2 px-12">
              <div className="h-3 bg-gray-100 rounded w-2/3" />
              <div className="h-3 bg-gray-100 rounded w-1/2" />
            </div>
          ) : subtopics.length === 0 ? (
            <p className="text-xs text-gray-400 py-2 text-center">
              No subtopics yet
            </p>
          ) : (
            subtopics.map((st) => (
              <SubtopicRow
                key={st.id}
                subtopic={st}
                topicName={topic.name}
                onEdit={() => onEditSubtopic(st)}
              />
            ))
          )}
        </>
      )}
    </div>
  );
}

export function SubjectDetailPanel({
  subjectId,
  subjectName: _subjectName,
  curriculumId,
  onAddTopic,
  onEditTopic,
  onAddSubtopic,
  onEditSubtopic,
}: SubjectDetailPanelProps) {
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());
  const { data: topics = [], isLoading } = useTopics(subjectId, curriculumId);

  const toggleTopic = (topicId: string) => {
    const next = new Set(expandedTopics);
    if (next.has(topicId)) next.delete(topicId);
    else next.add(topicId);
    setExpandedTopics(next);
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3 p-4">
        <div className="h-5 bg-gray-100 rounded w-1/2" />
        <div className="h-4 bg-gray-100 rounded w-3/4" />
        <div className="h-4 bg-gray-100 rounded w-2/3" />
      </div>
    );
  }

  if (topics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center px-6">
        <p className="text-sm text-gray-500 mb-4">No topics yet</p>
        <button
          onClick={onAddTopic}
          title="Add topic"
          className="flex items-center gap-2 px-3 py-2 bg-brand-primary text-white rounded-lg text-sm font-medium hover:bg-brand-primary/90"
        >
          <Plus className="w-4 h-4" />
          Add first topic
        </button>
      </div>
    );
  }

  // Group topics by grade
  const gradeGroups: { gradeId: string; gradeName: string; topics: Topic[] }[] =
    [];
  for (const topic of topics) {
    const gid = topic.grade_id ?? "unknown";
    const gname = topic.grade_name ?? "Unknown grade";
    const existing = gradeGroups.find((g) => g.gradeId === gid);
    if (existing) {
      existing.topics.push(topic);
    } else {
      gradeGroups.push({ gradeId: gid, gradeName: gname, topics: [topic] });
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100">
        <span className="font-['Inter'] text-xs font-bold uppercase tracking-widest text-gray-400">
          Topics
        </span>
        <button
          onClick={onAddTopic}
          title="Add topic"
          className="p-1.5 rounded-lg bg-brand-primary text-white hover:bg-brand-primary/90"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {gradeGroups.map(({ gradeId, gradeName, topics: gradeTopics }) => (
          <div key={gradeId}>
            <div className="flex items-center gap-2 px-4 py-1.5 bg-gray-50 border-b border-gray-100">
              <span className="flex-1 font-['Inter'] text-xs font-bold uppercase tracking-widest text-gray-400">
                {gradeName}
              </span>
            </div>
            {gradeTopics.map((topic) => (
              <TopicRow
                key={topic.curriculum_topic_id}
                topic={topic}
                curriculumId={curriculumId}
                isExpanded={expandedTopics.has(topic.topic_id)}
                onToggle={() => toggleTopic(topic.topic_id)}
                onEdit={() => onEditTopic(topic)}
                onAddSubtopic={(existingSubtopics) =>
                  onAddSubtopic(
                    topic.curriculum_topic_id,
                    topic.name,
                    existingSubtopics,
                  )
                }
                onEditSubtopic={(st) => onEditSubtopic(st, topic.name)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
