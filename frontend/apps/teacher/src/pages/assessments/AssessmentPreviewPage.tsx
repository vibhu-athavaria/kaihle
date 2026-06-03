import { useState } from "react";
import { useParams } from "react-router-dom";
import { DashboardLayout, Badge, Skeleton, Button } from "@kaihle/ui";
import {
  ChevronDown,
  ChevronRight,
  Edit3,
  AlertTriangle,
  Plus,
  RefreshCw,
  MessageSquare,
  Trash2,
} from "lucide-react";
import {
  useAssessmentPreview,
  type PreviewQuestion,
} from "../../hooks/useAssessmentPreview";
import { EditAssessmentDetailsModal } from "../../components/assessments/EditAssessmentDetailsModal";
import { AddQuestionModal } from "../../components/assessments/AddQuestionModal";
import { SuggestEditModal } from "../../components/assessments/SuggestEditModal";
import { ReplaceQuestionDrawer } from "../../components/assessments/ReplaceQuestionDrawer";
import { useRemoveQuestion } from "../../hooks/useAssessmentQuestions";

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  DRAFT: {
    label: "Draft",
    className: "bg-brand-border-soft text-brand-muted border-brand-border",
  },
  ACTIVE: {
    label: "Active",
    className: "bg-brand-green-light text-brand-green border-brand-green/30",
  },
  CLOSED: {
    label: "Closed",
    className: "bg-brand-border-soft text-brand-body border-brand-border",
  },
};

const TYPE_LABEL: Record<string, string> = {
  DIAGNOSTIC: "Diagnostic",
  TOPIC_SPECIFIC: "Topic Assessment",
  PROGRESS_CHECK: "Progress Check",
  FINAL: "Final Assessment",
};

const DIFFICULTY_STARS = (level: number) =>
  "⭐".repeat(Math.min(level, 5)) || "—";

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

export function AssessmentPreviewPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const [editOpen, setEditOpen] = useState(false);
  const [addQOpen, setAddQOpen] = useState(false);
  const [replaceQuestion, setReplaceQuestion] =
    useState<PreviewQuestion | null>(null);
  const [suggestQuestion, setSuggestQuestion] =
    useState<PreviewQuestion | null>(null);
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());
  const [removingId, setRemovingId] = useState<string | null>(null);

  const {
    data: assessment,
    isLoading,
    isError,
  } = useAssessmentPreview(assessmentId);
  const removeQuestion = useRemoveQuestion(assessmentId ?? "");

  if (isLoading) {
    return (
      <DashboardLayout variant="teacher" pageTitle="Assessment Preview">
        <div className="p-6 max-w-3xl mx-auto space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      </DashboardLayout>
    );
  }

  if (isError || !assessment) {
    return (
      <DashboardLayout variant="teacher" pageTitle="Assessment Preview">
        <div className="p-6 max-w-3xl mx-auto">
          <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-4">
            <p className="text-sm font-sans text-brand-red">
              Failed to load assessment preview. You may not have access to this
              assessment.
            </p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const statusBadge = STATUS_BADGE[assessment.status] ?? STATUS_BADGE.CLOSED;
  const topicGroups = groupByTopic(assessment.questions);

  // Build difficulty distribution
  const diffCount: Record<number, number> = {};
  for (const q of assessment.questions) {
    diffCount[q.difficulty_level] = (diffCount[q.difficulty_level] ?? 0) + 1;
  }
  const diffLevels = Object.keys(diffCount)
    .map(Number)
    .sort((a, b) => a - b);
  const maxCount =
    diffLevels.length > 0 ? Math.max(...Object.values(diffCount)) : 1;

  function toggleTopic(topicName: string) {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicName)) next.delete(topicName);
      else next.add(topicName);
      return next;
    });
  }

  return (
    <DashboardLayout variant="teacher" pageTitle="Assessment Preview">
      <div className="p-6 max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`inline-flex items-center text-[10px] font-sans font-bold uppercase tracking-widest px-2 py-0.5 rounded border ${statusBadge.className}`}
              >
                {statusBadge.label}
              </span>
              <span className="text-xs font-sans text-brand-muted">
                {TYPE_LABEL[assessment.assessment_type] ??
                  assessment.assessment_type}
              </span>
            </div>
            <h1 className="font-display font-bold text-xl text-brand-ink leading-tight">
              {assessment.title}
            </h1>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <Button
              variant="secondary"
              onClick={() => setAddQOpen(true)}
              className="flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" aria-hidden="true" />
              Add Question
            </Button>
            <Button
              variant="secondary"
              onClick={() => setEditOpen(true)}
              className="flex items-center gap-1.5"
            >
              <Edit3 className="w-4 h-4" aria-hidden="true" />
              Edit Details
            </Button>
          </div>
        </div>

        {/* Attempts warning */}
        {assessment.attempt_count > 0 && (
          <div className="flex items-start gap-3 bg-[#fffbeb] border border-[#fde68a] rounded-xl p-3">
            <AlertTriangle
              className="w-4 h-4 text-brand-gold-dark flex-shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <p className="text-xs font-sans text-brand-gold-dark leading-relaxed">
              <strong>
                {assessment.attempt_count} student
                {assessment.attempt_count === 1 ? "" : "s"}
              </strong>{" "}
              have started or completed this assessment. Question pool changes
              may affect in-progress attempts.
            </p>
          </div>
        )}

        {/* Stats bar */}
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-brand-light border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-primary leading-none">
              {assessment.questions.length}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">in pool</p>
          </div>
          <div className="bg-[#fffbeb] border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-gold leading-none">
              {assessment.question_count ?? "—"}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">
              per attempt
            </p>
          </div>
          <div className="bg-white border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-ink leading-none">
              {topicGroups.length}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">topics</p>
          </div>
          <div className="bg-white border border-brand-border rounded-xl p-3 text-center">
            <p className="font-sans font-extrabold text-2xl text-brand-ink leading-none">
              {assessment.time_limit_minutes > 0
                ? `${assessment.time_limit_minutes}m`
                : "∞"}
            </p>
            <p className="text-xs font-sans text-brand-muted mt-1">
              time limit
            </p>
          </div>
        </div>

        {/* Difficulty distribution chart */}
        {diffLevels.length > 0 && (
          <div className="bg-white border border-brand-border rounded-xl p-4">
            <p className="text-xs font-sans font-bold uppercase tracking-widest text-brand-muted mb-3">
              Difficulty distribution
            </p>
            <div className="flex items-end gap-2 h-10">
              {diffLevels.map((level) => {
                const count = diffCount[level] ?? 0;
                const heightPct = Math.round((count / maxCount) * 100);
                const isHigher = level > 3;
                return (
                  <div
                    key={level}
                    className="flex-1 flex flex-col items-center gap-1"
                  >
                    <div
                      className="w-full rounded-t"
                      style={{
                        height: `${heightPct}%`,
                        minHeight: "4px",
                        background: isHigher ? "#c9932a" : "#1a5c38",
                        opacity: 0.4 + level * 0.1,
                      }}
                      aria-label={`Level ${level}: ${count} questions`}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex gap-2 mt-2">
              {diffLevels.map((level) => (
                <div key={level} className="flex-1 text-center">
                  <p className="text-[10px] font-sans text-brand-muted">
                    Lvl {level}
                  </p>
                  <p className="text-[10px] font-sans font-bold text-brand-ink">
                    {diffCount[level] ?? 0}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Questions grouped by topic → subtopic */}
        <div>
          <p className="text-xs font-sans font-bold uppercase tracking-widest text-role-teacher-muted mb-3">
            Questions by topic
          </p>

          {topicGroups.length === 0 && (
            <div className="text-center py-12 px-6">
              <div className="text-3xl mb-3">📭</div>
              <p className="font-display font-bold text-base text-brand-ink mb-1">
                No questions in pool
              </p>
              <p className="text-sm font-sans text-brand-body">
                Use "Add Question" to add questions to this assessment.
              </p>
            </div>
          )}

          <div className="space-y-3">
            {topicGroups.map((group) => {
              const isExpanded = expandedTopics.has(group.topicName);
              const totalInTopic = [...group.subtopics.values()].reduce(
                (sum, qs) => sum + qs.length,
                0,
              );
              return (
                <div
                  key={group.topicName}
                  className="border border-brand-border rounded-xl overflow-hidden"
                >
                  {/* Topic header (accordion toggle) */}
                  <button
                    type="button"
                    onClick={() => toggleTopic(group.topicName)}
                    className="w-full flex items-center justify-between px-4 py-3 bg-brand-light hover:bg-brand-border-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-gold"
                    aria-expanded={isExpanded}
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown
                          className="w-4 h-4 text-brand-muted"
                          aria-hidden="true"
                        />
                      ) : (
                        <ChevronRight
                          className="w-4 h-4 text-brand-muted"
                          aria-hidden="true"
                        />
                      )}
                      <span className="text-sm font-sans font-semibold text-brand-ink">
                        {group.topicName}
                      </span>
                    </div>
                    <span className="text-xs font-sans text-brand-muted">
                      {totalInTopic} question{totalInTopic !== 1 ? "s" : ""}
                    </span>
                  </button>

                  {/* Subtopic groups */}
                  {isExpanded && (
                    <div className="divide-y divide-brand-border">
                      {[...group.subtopics.entries()].map(
                        ([subtopicName, questions]) => (
                          <div key={subtopicName} className="bg-white">
                            {/* Subtopic label */}
                            <p className="px-4 pt-3 pb-1 text-[10px] font-sans font-bold uppercase tracking-widest text-brand-muted">
                              {subtopicName}
                            </p>
                            {/* Question rows */}
                            {questions.map((q) => (
                              <div key={q.question_id}>
                                <div className="px-4 py-3 flex items-start gap-3 hover:bg-brand-light transition-colors">
                                  {/* Order badge */}
                                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-border-soft text-brand-body text-[10px] font-bold font-sans flex items-center justify-center mt-0.5">
                                    {q.order_index + 1}
                                  </span>

                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm font-sans text-brand-ink leading-snug">
                                      {q.question_text}
                                    </p>
                                    <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                                      <span className="inline-flex items-center gap-1 bg-brand-green-light border border-brand-green/30 rounded-md px-2 py-0.5 text-[11px] font-sans font-semibold text-brand-green">
                                        ✓ {q.correct_answer_key.toUpperCase()}
                                      </span>
                                      <Badge variant="neutral">
                                        {DIFFICULTY_STARS(q.difficulty_level)}{" "}
                                        Lvl {q.difficulty_level}
                                      </Badge>
                                      <Badge variant="info">
                                        {q.question_type}
                                      </Badge>
                                      {q.is_teacher_submitted && (
                                        <Badge variant="gold">
                                          Pending Review
                                        </Badge>
                                      )}
                                    </div>
                                    {q.explanation && (
                                      <p className="mt-1.5 text-xs font-sans text-brand-body italic">
                                        {q.explanation}
                                      </p>
                                    )}
                                  </div>

                                  {/* Per-question actions */}
                                  <div className="flex items-center gap-1 flex-shrink-0">
                                    <button
                                      type="button"
                                      onClick={() => setReplaceQuestion(q)}
                                      title="Replace question"
                                      className="w-7 h-7 rounded-lg flex items-center justify-center text-brand-muted hover:text-brand-ink hover:bg-brand-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                                    >
                                      <RefreshCw
                                        className="w-3.5 h-3.5"
                                        aria-hidden="true"
                                      />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setSuggestQuestion(q)}
                                      title="Suggest edit"
                                      className="w-7 h-7 rounded-lg flex items-center justify-center text-brand-muted hover:text-brand-ink hover:bg-brand-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
                                    >
                                      <MessageSquare
                                        className="w-3.5 h-3.5"
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
                                      title="Remove from pool"
                                      disabled={
                                        removeQuestion.isPending &&
                                        removingId === q.question_id
                                      }
                                      className="w-7 h-7 rounded-lg flex items-center justify-center text-brand-muted hover:text-brand-red hover:bg-brand-red-light transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-red disabled:opacity-40"
                                    >
                                      <Trash2
                                        className="w-3.5 h-3.5"
                                        aria-hidden="true"
                                      />
                                    </button>
                                  </div>
                                </div>

                                {/* Inline remove confirmation */}
                                {removingId === q.question_id && (
                                  <div className="mx-4 mb-3 flex items-center gap-2 bg-brand-red-light border border-brand-red/30 rounded-xl p-3">
                                    <p className="flex-1 text-xs font-sans text-brand-red">
                                      Remove this question?
                                      {(assessment?.attempt_count ?? 0) > 0
                                        ? " Students who answered it won't see it in the detail view."
                                        : ""}
                                    </p>
                                    <button
                                      type="button"
                                      onClick={() => setRemovingId(null)}
                                      className="text-xs font-sans font-bold text-brand-body hover:text-brand-ink px-2"
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
                                      className="text-xs font-sans font-bold text-brand-red hover:text-brand-red/80 px-2 disabled:opacity-50"
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

        {/* Modals */}
        {assessment && (
          <>
            <EditAssessmentDetailsModal
              open={editOpen}
              onOpenChange={setEditOpen}
              assessment={assessment}
              classId={assessment.id}
            />
            <AddQuestionModal
              open={addQOpen}
              onOpenChange={setAddQOpen}
              assessmentId={assessment.id}
              subtopics={[]}
            />
            <ReplaceQuestionDrawer
              open={replaceQuestion !== null}
              onOpenChange={(o) => {
                if (!o) setReplaceQuestion(null);
              }}
              assessmentId={assessment.id}
              question={replaceQuestion}
              hasResponses={assessment.attempt_count > 0}
            />
            <SuggestEditModal
              open={suggestQuestion !== null}
              onOpenChange={(o) => {
                if (!o) setSuggestQuestion(null);
              }}
              assessmentId={assessment.id}
              question={suggestQuestion}
            />
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
