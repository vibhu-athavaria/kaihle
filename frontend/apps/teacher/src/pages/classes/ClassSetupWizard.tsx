import { useState, useMemo, useCallback, useEffect } from "react";
import { Check, X } from "lucide-react";
import { Button, Modal } from "@kaihle/ui";
import {
  useClassTopics,
  useAvailableCurriculumTopics,
  useAddClassTopic,
  useRemoveClassTopic,
  useUpdateClassTopic,
  useReorderClassTopics,
  useDesignTier1Diagnostic,
  type ClassTopicItem,
  type AvailableCurriculumTopic,
} from "../../hooks/useClassTopics";
import { usePublishAssessment } from "../../hooks/useClassAssessments";
import { useClassTopicsWithGrades } from "../../hooks/useClassTopicsWithGrades";
import {
  useTopicAvailability,
  type TopicAvailability,
} from "../../hooks/useTopicAvailability";
import { TopicGroupSection } from "../../components/wizard/TopicGroupSection";
import { AssessmentConfigPanel } from "../../components/wizard/AssessmentConfigPanel";
import type { TopicWithAvailability } from "../../components/wizard/TopicRow";

interface ClassSetupWizardProps {
  classId: string;
  isOpen: boolean;
  onClose: () => void;
  /** Jump directly to step 2 when class already has topics */
  initialStep?: 1 | 2;
}

type Step = 1 | 2;

// ── Step 1: Topic list ────────────────────────────────────────────────────────

interface Step1Props {
  classId: string;
  onNext: () => void;
  onCancel: () => void;
}

function TopicListStep({ classId, onNext, onCancel }: Step1Props) {
  const { data: classTopics = [], isLoading: loadingTopics } =
    useClassTopics(classId);
  const { data: available = [], isLoading: loadingAvailable } =
    useAvailableCurriculumTopics(classId);

  const addTopic = useAddClassTopic(classId);
  const removeTopic = useRemoveClassTopic(classId);
  const updateTopic = useUpdateClassTopic(classId);
  const reorderTopics = useReorderClassTopics(classId);

  const [showPicker, setShowPicker] = useState(false);
  const [mutating, setMutating] = useState<string | null>(null);

  const sorted = useMemo(
    () => [...classTopics].sort((a, b) => a.sequence_order - b.sequence_order),
    [classTopics],
  );

  const covered = sorted.filter((t) => t.is_covered);
  const upcoming = sorted.filter((t) => !t.is_covered);

  async function handleAdd(topic: AvailableCurriculumTopic) {
    setMutating(topic.curriculum_topic_id);
    try {
      await addTopic.mutateAsync({
        curriculum_topic_id: topic.curriculum_topic_id,
        sequence_order: sorted.length,
      });
    } finally {
      setMutating(null);
    }
  }

  async function handleRemove(id: string) {
    setMutating(id);
    try {
      await removeTopic.mutateAsync(id);
    } finally {
      setMutating(null);
    }
  }

  async function handleMarkCovered(topic: ClassTopicItem) {
    setMutating(topic.id);
    try {
      await updateTopic.mutateAsync({
        topicId: topic.id,
        is_covered: !topic.is_covered,
      });
    } finally {
      setMutating(null);
    }
  }

  async function handleMove(index: number, direction: "up" | "down") {
    const reordered = [...sorted];
    const swapIdx = direction === "up" ? index - 1 : index + 1;
    if (swapIdx < 0 || swapIdx >= reordered.length) return;
    [reordered[index], reordered[swapIdx]] = [
      reordered[swapIdx],
      reordered[index],
    ];
    await reorderTopics.mutateAsync(
      reordered.map((t, i) => ({ id: t.id, sequence_order: i })),
    );
  }

  const loading = loadingTopics || loadingAvailable;

  function TopicRow({
    topic,
    isCovered,
    overallIndex,
  }: {
    topic: ClassTopicItem;
    isCovered: boolean;
    overallIndex: number;
  }) {
    return (
      <div
        className={[
          "flex items-center gap-3 px-[14px] py-3 border-b border-[#f3f4f6] last:border-b-0",
          isCovered ? "bg-[#fafffe]" : "bg-white",
        ].join(" ")}
      >
        {/* Drag-handle style up/down arrows (no library needed) */}
        <div className="flex flex-col gap-0.5 flex-shrink-0">
          <button
            type="button"
            disabled={overallIndex === 0 || reorderTopics.isPending}
            onClick={() => handleMove(overallIndex, "up")}
            aria-label={`Move ${topic.topic_name} up`}
            className="text-[#d1d5db] hover:text-[#c9932a] text-[10px] leading-none disabled:opacity-30 transition-colors"
          >
            ▲
          </button>
          <button
            type="button"
            disabled={
              overallIndex === sorted.length - 1 || reorderTopics.isPending
            }
            onClick={() => handleMove(overallIndex, "down")}
            aria-label={`Move ${topic.topic_name} down`}
            className="text-[#d1d5db] hover:text-[#c9932a] text-[10px] leading-none disabled:opacity-30 transition-colors"
          >
            ▼
          </button>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-[#374151] truncate">
            {topic.topic_name}
          </p>
          <p className="text-[11px] text-brand-muted mt-px">
            {topic.subtopic_count} subtopic
            {topic.subtopic_count !== 1 ? "s" : ""} · Seq.{" "}
            {topic.sequence_order + 1}
          </p>
        </div>

        {isCovered ? (
          <span className="flex-shrink-0 bg-[#f0fdf4] border border-[#d4e4d8] rounded-full px-[10px] py-[3px] text-[10px] font-bold text-[#1a5c38] whitespace-nowrap">
            ✓ Covered
          </span>
        ) : (
          <button
            type="button"
            disabled={mutating === topic.id}
            onClick={() => handleMarkCovered(topic)}
            className="flex-shrink-0 bg-white border border-[#e5e7eb] rounded-full px-[10px] py-1 text-[10px] font-semibold text-[#6b7280] hover:border-brand-gold hover:text-brand-gold transition-colors disabled:opacity-50 whitespace-nowrap"
          >
            Mark covered
          </button>
        )}

        {isCovered && (
          <button
            type="button"
            disabled={mutating === topic.id}
            onClick={() => handleMarkCovered(topic)}
            className="flex-shrink-0 bg-white border border-[#e5e7eb] rounded-full px-[10px] py-1 text-[10px] font-semibold text-[#6b7280] hover:border-brand-gold hover:text-brand-gold transition-colors disabled:opacity-50 whitespace-nowrap"
          >
            Unmark
          </button>
        )}

        <button
          type="button"
          disabled={mutating === topic.id}
          onClick={() => handleRemove(topic.id)}
          aria-label={`Remove ${topic.topic_name}`}
          className="flex-shrink-0 w-7 h-7 rounded-[6px] bg-[#fee2e2] flex items-center justify-center text-[#dc2626] hover:bg-red-200 transition-colors disabled:opacity-50"
        >
          <X className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-display font-bold text-lg text-brand-ink mb-1">
          Choose and order your topics
        </h3>
        <p className="text-xs text-brand-body">
          Select all topics you'll cover this year. Reorder with the arrows.
          Mark any you've already taught as covered — they'll appear first.
        </p>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-14 bg-gray-100 rounded-lg animate-pulse"
            />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-8 text-sm text-brand-muted">
          No topics added yet. Use the button below to add from the curriculum.
        </div>
      ) : (
        <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
          {covered.length > 0 && (
            <>
              <div className="px-[14px] py-2 text-[10px] font-bold uppercase tracking-[0.6px] bg-[#f0fdf4] border-b border-[#d4e4d8] text-[#1a5c38]">
                Already covered ({covered.length})
              </div>
              {covered.map((t) => (
                <TopicRow
                  key={t.id}
                  topic={t}
                  isCovered={true}
                  overallIndex={sorted.indexOf(t)}
                />
              ))}
            </>
          )}
          {upcoming.length > 0 && (
            <>
              <div className="px-[14px] py-2 text-[10px] font-bold uppercase tracking-[0.6px] bg-[#fffbeb] border-b border-[#fde68a] text-[#92400e]">
                To be taught ({upcoming.length})
              </div>
              {upcoming.map((t) => (
                <TopicRow
                  key={t.id}
                  topic={t}
                  isCovered={false}
                  overallIndex={sorted.indexOf(t)}
                />
              ))}
            </>
          )}
        </div>
      )}

      {/* Dashed add-topic button */}
      <button
        type="button"
        onClick={() => setShowPicker((v) => !v)}
        className="w-full border-2 border-dashed border-[#e5e7eb] rounded-lg py-[13px] text-xs text-brand-muted hover:border-brand-gold hover:text-brand-gold transition-colors"
      >
        {showPicker
          ? "↑ Hide curriculum topics"
          : "+ Add topic from curriculum"}
      </button>

      {/* Expandable curriculum picker */}
      {showPicker && (
        <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
          <div className="px-3 py-2.5 bg-gray-50 border-b border-[#e5e7eb]">
            <p className="text-[10px] font-bold uppercase tracking-wider text-brand-muted">
              Curriculum Topics
              {available.length > 0 && (
                <span className="ml-1.5 font-medium normal-case tracking-normal text-gray-400">
                  — {available.length} remaining
                </span>
              )}
            </p>
          </div>
          <div className="p-2 space-y-1 max-h-48 overflow-y-auto">
            {available.length === 0 ? (
              <p className="text-center py-4 text-xs text-brand-muted">
                All curriculum topics already added.
              </p>
            ) : (
              available.map((t: AvailableCurriculumTopic) => (
                <div
                  key={t.curriculum_topic_id}
                  className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg hover:bg-gray-50"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-brand-ink truncate">
                      {t.topic_name}
                    </p>
                    <p className="text-[10px] text-brand-muted">
                      {t.subtopic_count} subtopic
                      {t.subtopic_count !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={mutating === t.curriculum_topic_id}
                    onClick={() => handleAdd(t)}
                    aria-label={`Add ${t.topic_name}`}
                    className="flex-shrink-0 rounded-full bg-brand-primary/10 text-brand-primary hover:bg-brand-primary hover:text-white transition-all px-3 py-1 text-[10px] font-bold disabled:opacity-50"
                  >
                    + Add
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <div className="flex justify-end pt-1">
        <div className="flex gap-3">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={onNext}
            disabled={sorted.length === 0}
          >
            Next: Design Diagnostic →
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Step 2: Diagnostic builder (redesigned) ──────────────────────────────────

interface Step2Props {
  classId: string;
  onBack: () => void;
  onDone: () => void;
}

function DiagnosticBuilderStep({ classId, onBack, onDone }: Step2Props) {
  const { data: gradeTopics, isLoading: loadingTopics } =
    useClassTopicsWithGrades(classId);

  // ── Config state ────────────────────────────────────────────────────────────
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(
    new Set(),
  );
  const [questionsPerTopic, setQuestionsPerTopic] = useState(2);
  const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | null>(null);
  const [questionTypes, setQuestionTypes] = useState<string[]>(["MCQ"]);
  const [minimumDifficulty, setMinimumDifficulty] = useState(1);
  const [maximumDifficulty, setMaximumDifficulty] = useState(5);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Debounced topic IDs for the availability query (300ms)
  const [debouncedTopicIds, setDebouncedTopicIds] = useState<string[]>([]);
  const [debouncedQpt, setDebouncedQpt] = useState(questionsPerTopic);
  const [debouncedMin, setDebouncedMin] = useState(minimumDifficulty);
  const [debouncedMax, setDebouncedMax] = useState(maximumDifficulty);
  const [debouncedTypes, setDebouncedTypes] = useState(questionTypes);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedTopicIds(Array.from(selectedTopicIds));
      setDebouncedQpt(questionsPerTopic);
      setDebouncedMin(minimumDifficulty);
      setDebouncedMax(maximumDifficulty);
      setDebouncedTypes(questionTypes);
    }, 300);
    return () => clearTimeout(t);
  }, [
    selectedTopicIds,
    questionsPerTopic,
    minimumDifficulty,
    maximumDifficulty,
    questionTypes,
  ]);

  const { data: availability, isLoading: availLoading } = useTopicAvailability({
    classId,
    topicIds: debouncedTopicIds,
    questionsPerTopic: debouncedQpt,
    minimumDifficulty: debouncedMin,
    maximumDifficulty: debouncedMax,
    questionTypes: debouncedTypes,
  });

  // Build availability map keyed by curriculum_topic_id
  const availMap = useMemo(() => {
    const m = new Map<string, TopicAvailability>();
    availability?.forEach((a) => m.set(a.curriculum_topic_id, a));
    return m;
  }, [availability]);

  // Merge availability into topic objects
  function enrichTopics(
    topics: {
      curriculum_topic_id: string;
      topic_name: string;
      grade_level: number;
      subtopic_count: number;
    }[],
  ): TopicWithAvailability[] {
    return topics.map((t) => ({
      ...t,
      availability: availMap.get(t.curriculum_topic_id),
      availabilityLoading:
        availLoading && selectedTopicIds.has(t.curriculum_topic_id),
    }));
  }

  const currentTopics = enrichTopics(gradeTopics?.current_grade_topics ?? []);
  const previousTopics = enrichTopics(gradeTopics?.previous_grade_topics ?? []);

  const toggleTopic = useCallback((id: string) => {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllCurrent = useCallback(() => {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      currentTopics.forEach((t) => next.add(t.curriculum_topic_id));
      return next;
    });
  }, [currentTopics]);

  const selectAllPrevious = useCallback(() => {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      previousTopics.forEach((t) => next.add(t.curriculum_topic_id));
      return next;
    });
  }, [previousTopics]);

  // Validation
  const selectedAvailabilities = Array.from(selectedTopicIds)
    .map((id) => availMap.get(id))
    .filter((a): a is TopicAvailability => a !== undefined);

  const errorTopics = selectedAvailabilities.filter(
    (a) => a.available_questions === 0,
  );
  const warnTopics = selectedAvailabilities.filter(
    (a) =>
      a.available_questions > 0 && a.available_questions < questionsPerTopic,
  );

  const canSubmit =
    selectedTopicIds.size > 0 &&
    errorTopics.length === 0 &&
    questionTypes.length > 0 &&
    minimumDifficulty <= maximumDifficulty;

  const designDiagnostic = useDesignTier1Diagnostic(classId);
  const publishAssessment = usePublishAssessment(classId);

  async function handleSubmit() {
    if (!canSubmit) {
      if (selectedTopicIds.size === 0)
        setError("Select at least one topic for the diagnostic.");
      else if (errorTopics.length > 0)
        setError(
          "Remove topics with no questions in the bank before publishing.",
        );
      else if (questionTypes.length === 0)
        setError("Select at least one question type.");
      else setError("Minimum difficulty cannot exceed maximum.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const assessment = await designDiagnostic.mutateAsync({
        topic_ids: Array.from(selectedTopicIds),
        questions_per_topic: questionsPerTopic,
        time_limit_minutes: timeLimitMinutes,
        question_types: questionTypes,
        minimum_difficulty: minimumDifficulty,
        maximum_difficulty: maximumDifficulty,
      });
      await publishAssessment.mutateAsync(String(assessment.id));
      onDone();
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const estimatedTotal = selectedTopicIds.size * questionsPerTopic;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-display font-bold text-[17px] text-brand-ink mb-1">
          Design your Tier 1 diagnostic
        </h3>
        <p className="text-[12px] text-brand-body">
          Choose topics to baseline — include previous grade topics to check
          prior knowledge. Configure how many questions per topic and timing.
        </p>
      </div>

      {/* Locked warning */}
      <div className="bg-[#fffbeb] border border-[#fde68a] rounded-[6px] px-3 py-[9px] text-[11px] text-[#92400e]">
        ⚠ Once a student submits an attempt, this diagnostic is locked and
        cannot be edited.
      </div>

      {/* Amber warning banner (warn topics) */}
      {warnTopics.length > 0 && (
        <div className="bg-[#fffbeb] border border-[#fde68a] rounded-[8px] px-3 py-[10px] text-[11px] text-[#92400e] flex gap-2 items-start">
          <span>⚠</span>
          <span>
            {warnTopics.length} topic
            {warnTopics.length !== 1 ? "s" : ""} have fewer questions than
            requested. The diagnostic will use what&apos;s available for those
            topics.
          </span>
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-5 items-start">
        {/* LEFT: topic picker */}
        <div className="flex-1 min-w-0">
          <div className="border border-[#e5e7eb] rounded-[8px] overflow-hidden">
            {/* Card header */}
            <div className="px-[14px] py-[10px] bg-[#f9fafb] border-b border-[#e5e7eb] flex items-center justify-between">
              <span className="text-[11px] font-bold text-[#374151]">
                Select topics to test
              </span>
              <span className="text-[11px] text-brand-muted">
                {selectedTopicIds.size} selected · ~{estimatedTotal} questions
                total
              </span>
            </div>

            {loadingTopics ? (
              <div className="p-3 space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className="h-10 bg-gray-100 rounded animate-pulse"
                  />
                ))}
              </div>
            ) : (
              <>
                {/* Current grade section */}
                {currentTopics.length > 0 && (
                  <TopicGroupSection
                    gradeLabel={`Current Grade (Grade ${gradeTopics!.current_grade_level})`}
                    isCurrent={true}
                    topics={currentTopics}
                    selectedIds={selectedTopicIds}
                    questionsPerTopic={questionsPerTopic}
                    onToggle={toggleTopic}
                    onSelectAll={selectAllCurrent}
                    defaultOpen={true}
                  />
                )}

                {/* Previous grade section */}
                {previousTopics.length > 0 && (
                  <TopicGroupSection
                    gradeLabel={`Previous Grade (Grade ${gradeTopics!.previous_grade_level})`}
                    isCurrent={false}
                    topics={previousTopics}
                    selectedIds={selectedTopicIds}
                    questionsPerTopic={questionsPerTopic}
                    onToggle={toggleTopic}
                    onSelectAll={selectAllPrevious}
                    defaultOpen={false}
                  />
                )}
              </>
            )}

            {/* Summary bar */}
            <div className="px-[14px] py-[7px] bg-[rgba(245,234,208,0.3)] border-t border-[#e5e7eb] flex items-center justify-between">
              <span className="text-[11px] font-bold text-brand-ink">
                {selectedTopicIds.size} topic
                {selectedTopicIds.size !== 1 ? "s" : ""} selected
              </span>
              {errorTopics.length + warnTopics.length > 0 && (
                <span className="text-[11px] text-[#92400e]">
                  {errorTopics.length + warnTopics.length} topic
                  {errorTopics.length + warnTopics.length !== 1 ? "s" : ""} need
                  attention ⚠
                </span>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: config panel (sticky) */}
        <div className="w-[236px] flex-shrink-0">
          <AssessmentConfigPanel
            questionsPerTopic={questionsPerTopic}
            onQuestionsPerTopicChange={setQuestionsPerTopic}
            timeLimitMinutes={timeLimitMinutes}
            onTimeLimitChange={setTimeLimitMinutes}
            questionTypes={questionTypes}
            onQuestionTypesChange={setQuestionTypes}
            minimumDifficulty={minimumDifficulty}
            maximumDifficulty={maximumDifficulty}
            onDifficultyChange={(min, max) => {
              setMinimumDifficulty(min);
              setMaximumDifficulty(max);
            }}
          />
        </div>
      </div>

      {error && (
        <div className="text-xs text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <Button type="button" variant="secondary" onClick={onBack}>
          ← Back to Topics
        </Button>
        <Button
          type="button"
          variant="primary"
          loading={submitting}
          disabled={submitting || !canSubmit}
          onClick={handleSubmit}
        >
          Publish Diagnostic &amp; Finish Setup
        </Button>
      </div>
    </div>
  );
}

// ── Wizard shell ──────────────────────────────────────────────────────────────

export function ClassSetupWizard({
  classId,
  isOpen,
  onClose,
  initialStep = 1,
}: ClassSetupWizardProps) {
  const [step, setStep] = useState<Step>(initialStep);
  const [done, setDone] = useState(false);

  function handleClose() {
    setStep(initialStep);
    setDone(false);
    onClose();
  }

  return (
    <Modal
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
      title="Class Curriculum Setup"
      maxWidth="xl"
    >
      <div className="mt-2">
        {/* Step indicator */}
        <div className="flex items-center gap-3 mb-5">
          <div
            className={[
              "w-[26px] h-[26px] rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0",
              step === 1
                ? "bg-brand-gold text-white"
                : "bg-brand-primary text-white",
            ].join(" ")}
            aria-current={step === 1 ? "step" : undefined}
          >
            {step > 1 ? (
              <Check className="w-3.5 h-3.5" aria-hidden="true" />
            ) : (
              "1"
            )}
          </div>
          <span
            className={[
              "text-xs font-bold",
              step === 1
                ? "text-brand-gold"
                : step > 1
                  ? "text-brand-primary"
                  : "text-brand-muted",
            ].join(" ")}
          >
            Topics
          </span>
          <div
            className={[
              "flex-1 h-0.5 rounded",
              step > 1 ? "bg-brand-gold" : "bg-gray-200",
            ].join(" ")}
          />
          <div
            className={[
              "w-[26px] h-[26px] rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0",
              step === 2
                ? "bg-brand-gold text-white"
                : "bg-gray-200 text-gray-400",
            ].join(" ")}
            aria-current={step === 2 ? "step" : undefined}
          >
            2
          </div>
          <span
            className={[
              "text-xs font-bold",
              step === 2 ? "text-brand-gold" : "text-brand-muted",
            ].join(" ")}
          >
            Diagnostic
          </span>
        </div>

        {done ? (
          <div className="text-center py-8 space-y-3">
            <div className="w-12 h-12 rounded-full bg-brand-green-light flex items-center justify-center mx-auto">
              <Check
                className="w-6 h-6 text-brand-primary"
                aria-hidden="true"
              />
            </div>
            <h3 className="font-display font-bold text-lg text-brand-ink">
              Diagnostic published!
            </h3>
            <p className="text-sm text-brand-body">
              Your Tier 1 diagnostic is live. Students will see it when they
              open this class.
            </p>
            <Button
              type="button"
              variant="primary"
              onClick={handleClose}
              className="mt-2"
            >
              Done
            </Button>
          </div>
        ) : step === 1 ? (
          <TopicListStep
            classId={classId}
            onNext={() => setStep(2)}
            onCancel={handleClose}
          />
        ) : (
          <DiagnosticBuilderStep
            classId={classId}
            onBack={() => setStep(1)}
            onDone={() => setDone(true)}
          />
        )}
      </div>
    </Modal>
  );
}
