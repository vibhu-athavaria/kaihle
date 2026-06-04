import { useState } from "react";
import { SlideOverPanel, Badge, Skeleton } from "@kaihle/ui";
import {
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  RefreshCw,
  MessageSquare,
  Trash2,
} from "lucide-react";
import {
  useAssessmentPreview,
  type PreviewQuestion,
} from "../../hooks/useAssessmentPreview";
import { useRemoveQuestion } from "../../hooks/useAssessmentQuestions";
import { AddQuestionModal } from "./AddQuestionModal";
import { ReplaceQuestionDrawer } from "./ReplaceQuestionDrawer";
import { SuggestEditModal } from "./SuggestEditModal";
import { EditAssessmentDetailsModal } from "./EditAssessmentDetailsModal";

interface Props {
  open: boolean;
  assessmentId: string;
  classId: string;
  onClose: () => void;
}

interface TopicGroup {
  topicName: string;
  subtopics: Map<string, PreviewQuestion[]>;
}

function groupByTopic(questions: PreviewQuestion[]): TopicGroup[] {
  const topicMap = new Map<string, TopicGroup>();
  for (const q of questions) {
    if (!topicMap.has(q.topic_name)) {
      topicMap.set(q.topic_name, {
        topicName: q.topic_name,
        subtopics: new Map(),
      });
    }
    const group = topicMap.get(q.topic_name)!;
    if (!group.subtopics.has(q.subtopic_name)) {
      group.subtopics.set(q.subtopic_name, []);
    }
    group.subtopics.get(q.subtopic_name)!.push(q);
  }
  return [...topicMap.values()];
}

export function AssessmentPreviewDrawer({
  open,
  assessmentId,
  classId,
  onClose,
}: Props) {
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [addQOpen, setAddQOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [replaceQuestion, setReplaceQuestion] =
    useState<PreviewQuestion | null>(null);
  const [suggestQuestion, setSuggestQuestion] =
    useState<PreviewQuestion | null>(null);

  const {
    data: assessment,
    isLoading,
    isError,
  } = useAssessmentPreview(open ? assessmentId : undefined);
  const removeQuestion = useRemoveQuestion(assessmentId);

  function toggleTopic(name: string) {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  const topicGroups = assessment ? groupByTopic(assessment.questions) : [];

  const diffCount: Record<number, number> = {};
  for (const q of assessment?.questions ?? []) {
    diffCount[q.difficulty_level] = (diffCount[q.difficulty_level] ?? 0) + 1;
  }
  const diffLevels = Object.keys(diffCount)
    .map(Number)
    .sort((a, b) => a - b);
  const maxCount =
    diffLevels.length > 0 ? Math.max(...Object.values(diffCount)) : 1;

  return (
    <>
      <SlideOverPanel
        open={open}
        title={assessment?.title ?? "Assessment Preview"}
        onClose={onClose}
        width="w-[520px]"
        footer={
          assessment ? (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setAddQOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-sans font-semibold border border-brand-border text-brand-body hover:text-brand-ink hover:border-brand-gold-mid transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
              >
                + Add Question
              </button>
              <button
                type="button"
                onClick={() => setEditOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-sans font-semibold border border-brand-border text-brand-body hover:text-brand-ink hover:border-brand-gold-mid transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
              >
                Edit Details
              </button>
            </div>
          ) : undefined
        }
      >
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        )}

        {isError && (
          <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
            <p className="text-sm font-sans text-brand-red">
              Failed to load preview. You may not have access to this
              assessment.
            </p>
          </div>
        )}

        {assessment && (
          <div className="space-y-5">
            {/* Attempts warning */}
            {assessment.attempt_count > 0 && (
              <div className="flex items-start gap-2 bg-[#fffbeb] border border-[#fde68a] rounded-xl p-3">
                <AlertTriangle
                  className="w-4 h-4 text-brand-gold-dark flex-shrink-0 mt-0.5"
                  aria-hidden="true"
                />
                <p className="text-xs font-sans text-brand-gold-dark leading-relaxed">
                  <strong>
                    {assessment.attempt_count} student
                    {assessment.attempt_count === 1 ? "" : "s"}
                  </strong>{" "}
                  have started this assessment. Pool changes may affect
                  in-progress attempts.
                </p>
              </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-brand-light border border-brand-border rounded-xl p-2.5 text-center">
                <p className="font-sans font-extrabold text-xl text-brand-primary leading-none">
                  {assessment.questions.length}
                </p>
                <p className="text-[10px] font-sans text-brand-muted mt-0.5">
                  in pool
                </p>
              </div>
              <div className="bg-[#fffbeb] border border-brand-border rounded-xl p-2.5 text-center">
                <p className="font-sans font-extrabold text-xl text-brand-gold leading-none">
                  {assessment.question_count ?? "—"}
                </p>
                <p className="text-[10px] font-sans text-brand-muted mt-0.5">
                  per attempt
                </p>
              </div>
              <div className="bg-white border border-brand-border rounded-xl p-2.5 text-center">
                <p className="font-sans font-extrabold text-xl text-brand-ink leading-none">
                  {assessment.time_limit_minutes > 0
                    ? `${assessment.time_limit_minutes}m`
                    : "∞"}
                </p>
                <p className="text-[10px] font-sans text-brand-muted mt-0.5">
                  time limit
                </p>
              </div>
            </div>

            {/* Difficulty distribution */}
            {diffLevels.length > 0 && (
              <div className="bg-white border border-brand-border rounded-xl p-3">
                <p className="text-[10px] font-sans font-bold uppercase tracking-widest text-brand-muted mb-2">
                  Difficulty distribution
                </p>
                <div className="flex items-end gap-1.5 h-8">
                  {diffLevels.map((level) => {
                    const count = diffCount[level] ?? 0;
                    const heightPct = Math.round((count / maxCount) * 100);
                    return (
                      <div
                        key={level}
                        className="flex-1 flex flex-col items-center gap-0.5"
                      >
                        <div
                          className="w-full rounded-t"
                          style={{
                            height: `${heightPct}%`,
                            minHeight: "3px",
                            background: level > 3 ? "#c9932a" : "#1a5c38",
                            opacity: 0.4 + level * 0.1,
                          }}
                          aria-label={`Level ${level}: ${count}`}
                        />
                      </div>
                    );
                  })}
                </div>
                <div className="flex gap-1.5 mt-1">
                  {diffLevels.map((level) => (
                    <div key={level} className="flex-1 text-center">
                      <p className="text-[9px] font-sans text-brand-muted">
                        L{level}
                      </p>
                      <p className="text-[9px] font-sans font-bold text-brand-ink">
                        {diffCount[level]}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Questions by topic */}
            <div>
              <p className="text-[10px] font-sans font-bold uppercase tracking-widest text-brand-muted mb-2">
                Questions by topic
              </p>

              {topicGroups.length === 0 && (
                <p className="text-sm font-sans text-brand-muted text-center py-8">
                  No questions in pool yet.
                </p>
              )}

              <div className="space-y-2">
                {topicGroups.map((group) => {
                  const isExpanded = expandedTopics.has(group.topicName);
                  const total = [...group.subtopics.values()].reduce(
                    (s, qs) => s + qs.length,
                    0,
                  );
                  return (
                    <div
                      key={group.topicName}
                      className="border border-brand-border rounded-xl overflow-hidden"
                    >
                      <button
                        type="button"
                        onClick={() => toggleTopic(group.topicName)}
                        className="w-full flex items-center justify-between px-3 py-2.5 bg-brand-light hover:bg-brand-border-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-gold"
                        aria-expanded={isExpanded}
                      >
                        <div className="flex items-center gap-2">
                          {isExpanded ? (
                            <ChevronDown
                              className="w-3.5 h-3.5 text-brand-muted"
                              aria-hidden="true"
                            />
                          ) : (
                            <ChevronRight
                              className="w-3.5 h-3.5 text-brand-muted"
                              aria-hidden="true"
                            />
                          )}
                          <span className="text-sm font-sans font-semibold text-brand-ink">
                            {group.topicName}
                          </span>
                        </div>
                        <span className="text-xs font-sans text-brand-muted">
                          {total}q
                        </span>
                      </button>

                      {isExpanded && (
                        <div className="divide-y divide-brand-border bg-white">
                          {[...group.subtopics.entries()].map(
                            ([subtopicName, questions]) => (
                              <div key={subtopicName}>
                                <p className="px-4 pt-2.5 pb-1 text-[9px] font-sans font-bold uppercase tracking-widest text-brand-muted">
                                  {subtopicName}
                                </p>
                                {questions.map((q) => (
                                  <div key={q.question_id}>
                                    <div className="px-4 py-2.5 flex items-start gap-2.5">
                                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-border-soft text-brand-body text-[9px] font-bold font-sans flex items-center justify-center mt-0.5">
                                        {q.order_index + 1}
                                      </span>
                                      <div className="flex-1 min-w-0">
                                        <p className="text-xs font-sans text-brand-ink leading-snug">
                                          {q.question_text}
                                        </p>
                                        <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
                                          <span className="inline-flex items-center gap-0.5 bg-brand-green-light border border-brand-green/30 rounded px-1.5 py-0.5 text-[10px] font-sans font-semibold text-brand-green">
                                            ✓{" "}
                                            {q.correct_answer_key.toUpperCase()}
                                          </span>
                                          <Badge variant="neutral">
                                            Lvl {q.difficulty_level}
                                          </Badge>
                                          {q.is_teacher_submitted && (
                                            <Badge variant="gold">
                                              Pending
                                            </Badge>
                                          )}
                                        </div>
                                      </div>
                                      {/* Actions */}
                                      <div className="flex items-center gap-0.5 flex-shrink-0">
                                        <button
                                          type="button"
                                          onClick={() => setReplaceQuestion(q)}
                                          title="Replace"
                                          className="w-6 h-6 rounded flex items-center justify-center text-brand-muted hover:text-brand-ink hover:bg-brand-light transition-colors"
                                        >
                                          <RefreshCw
                                            className="w-3 h-3"
                                            aria-hidden="true"
                                          />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setSuggestQuestion(q)}
                                          title="Suggest edit"
                                          className="w-6 h-6 rounded flex items-center justify-center text-brand-muted hover:text-brand-ink hover:bg-brand-light transition-colors"
                                        >
                                          <MessageSquare
                                            className="w-3 h-3"
                                            aria-hidden="true"
                                          />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setRemovingId(
                                              removingId === q.question_id
                                                ? null
                                                : q.question_id,
                                            )
                                          }
                                          title="Remove"
                                          className="w-6 h-6 rounded flex items-center justify-center text-brand-muted hover:text-brand-red hover:bg-brand-red-light transition-colors"
                                        >
                                          <Trash2
                                            className="w-3 h-3"
                                            aria-hidden="true"
                                          />
                                        </button>
                                      </div>
                                    </div>
                                    {/* Inline remove confirmation */}
                                    {removingId === q.question_id && (
                                      <div className="mx-4 mb-2 flex items-center gap-2 bg-brand-red-light border border-brand-red/30 rounded-lg p-2.5">
                                        <p className="flex-1 text-[11px] font-sans text-brand-red">
                                          Remove this question?
                                        </p>
                                        <button
                                          type="button"
                                          onClick={() => setRemovingId(null)}
                                          className="text-[11px] font-sans font-bold text-brand-body px-2"
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          type="button"
                                          onClick={async () => {
                                            await removeQuestion.mutateAsync(
                                              q.question_id,
                                            );
                                            setRemovingId(null);
                                          }}
                                          disabled={removeQuestion.isPending}
                                          className="text-[11px] font-sans font-bold text-brand-red px-2 disabled:opacity-50"
                                        >
                                          {removeQuestion.isPending
                                            ? "Removing…"
                                            : "Remove"}
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ),
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </SlideOverPanel>

      {/* Sub-modals (rendered outside SlideOverPanel to avoid stacking context issues) */}
      {assessment && (
        <>
          <AddQuestionModal
            open={addQOpen}
            onOpenChange={setAddQOpen}
            assessmentId={assessmentId}
            subtopics={[]}
          />
          <EditAssessmentDetailsModal
            open={editOpen}
            onOpenChange={setEditOpen}
            assessment={assessment}
            classId={classId}
          />
          <ReplaceQuestionDrawer
            open={replaceQuestion !== null}
            onOpenChange={(o) => {
              if (!o) setReplaceQuestion(null);
            }}
            assessmentId={assessmentId}
            question={replaceQuestion}
            hasResponses={assessment.attempt_count > 0}
          />
          <SuggestEditModal
            open={suggestQuestion !== null}
            onOpenChange={(o) => {
              if (!o) setSuggestQuestion(null);
            }}
            assessmentId={assessmentId}
            question={suggestQuestion}
          />
        </>
      )}
    </>
  );
}
