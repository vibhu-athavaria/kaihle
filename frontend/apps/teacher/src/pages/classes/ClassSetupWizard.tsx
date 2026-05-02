import { useState, useMemo } from "react";
import {
  Check,
  ChevronUp,
  ChevronDown,
  Minus,
  Plus,
  Search,
} from "lucide-react";
import { Button, Modal } from "@kaihle/ui";
import {
  useClassTopics,
  useAvailableCurriculumTopics,
  useAddClassTopic,
  useRemoveClassTopic,
  useReorderClassTopics,
  useDesignTier1Diagnostic,
  type ClassTopicItem,
  type AvailableCurriculumTopic,
} from "../../hooks/useClassTopics";

interface ClassSetupWizardProps {
  classId: string;
  isOpen: boolean;
  onClose: () => void;
  /** Jump directly to step 2 when class already has topics */
  initialStep?: 1 | 2;
}

type Step = 1 | 2;

// ── Step 1: Topic picker ──────────────────────────────────────────────────────

interface Step1Props {
  classId: string;
  onNext: () => void;
  onCancel: () => void;
}

function TopicPickerStep({ classId, onNext, onCancel }: Step1Props) {
  const { data: classTopics = [], isLoading: loadingTopics } =
    useClassTopics(classId);
  const { data: available = [], isLoading: loadingAvailable } =
    useAvailableCurriculumTopics(classId);

  const addTopic = useAddClassTopic(classId);
  const removeTopic = useRemoveClassTopic(classId);
  const reorderTopics = useReorderClassTopics(classId);

  const [search, setSearch] = useState("");
  const [mutating, setMutating] = useState<string | null>(null);

  const sortedClassTopics = useMemo(
    () => [...classTopics].sort((a, b) => a.sequence_order - b.sequence_order),
    [classTopics],
  );

  const filteredAvailable = useMemo(() => {
    const q = search.toLowerCase();
    return available.filter((t) => t.topic_name.toLowerCase().includes(q));
  }, [available, search]);

  async function handleAdd(topic: AvailableCurriculumTopic) {
    setMutating(topic.id);
    try {
      await addTopic.mutateAsync({
        curriculum_topic_id: topic.id,
        sequence_order: sortedClassTopics.length,
      });
    } finally {
      setMutating(null);
    }
  }

  async function handleRemove(topicId: string) {
    setMutating(topicId);
    try {
      await removeTopic.mutateAsync(topicId);
    } finally {
      setMutating(null);
    }
  }

  async function handleMove(index: number, direction: "up" | "down") {
    const reordered = [...sortedClassTopics];
    const swapIdx = direction === "up" ? index - 1 : index + 1;
    [reordered[index], reordered[swapIdx]] = [
      reordered[swapIdx],
      reordered[index],
    ];
    const items = reordered.map((t, i) => ({
      id: t.id,
      sequence_order: i,
    }));
    await reorderTopics.mutateAsync(items);
  }

  const loading = loadingTopics || loadingAvailable;

  return (
    <div className="space-y-5">
      <p className="text-sm text-brand-body">
        Choose which curriculum topics this class will cover. Students will see
        topics in the order you set here.
      </p>

      <div className="grid grid-cols-2 gap-4">
        {/* Left: available curriculum topics */}
        <div className="border border-role-teacher-border rounded-xl overflow-hidden">
          <div className="px-3 py-2.5 bg-gray-50 border-b border-role-teacher-border">
            <p className="text-[10px] font-bold uppercase tracking-wider text-role-teacher-muted">
              Curriculum Topics
              {available.length > 0 && (
                <span className="ml-1.5 font-medium normal-case tracking-normal text-gray-400">
                  — {available.length} remaining
                </span>
              )}
            </p>
          </div>

          <div className="p-2">
            <div className="relative mb-2">
              <Search
                className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
                aria-hidden="true"
              />
              <input
                type="text"
                placeholder="Search topics…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-brand-border bg-white text-brand-ink font-sans text-xs focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
              />
            </div>

            <div className="space-y-1 max-h-64 overflow-y-auto">
              {loading && (
                <div className="space-y-1.5 p-1">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="h-9 rounded-lg bg-gray-100 animate-pulse"
                    />
                  ))}
                </div>
              )}

              {!loading && filteredAvailable.length === 0 && (
                <p className="text-center py-6 text-xs text-brand-muted">
                  {available.length === 0
                    ? "All topics added to class."
                    : "No topics match your search."}
                </p>
              )}

              {filteredAvailable.map((t) => (
                <div
                  key={t.id}
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
                    disabled={mutating === t.id}
                    onClick={() => handleAdd(t)}
                    aria-label={`Add ${t.topic_name}`}
                    className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-primary/10 text-brand-primary hover:bg-brand-primary hover:text-white transition-all flex items-center justify-center disabled:opacity-50"
                  >
                    <Plus className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: class topic list (ordered) */}
        <div className="border border-role-teacher-border rounded-xl overflow-hidden">
          <div className="px-3 py-2.5 bg-gray-50 border-b border-role-teacher-border">
            <p className="text-[10px] font-bold uppercase tracking-wider text-role-teacher-muted">
              Class Topics
              {sortedClassTopics.length > 0 && (
                <span className="ml-1.5 font-medium normal-case tracking-normal text-gray-400">
                  — {sortedClassTopics.length} selected
                </span>
              )}
            </p>
          </div>

          <div className="p-2 space-y-1 max-h-[296px] overflow-y-auto">
            {!loading && sortedClassTopics.length === 0 && (
              <p className="text-center py-8 text-xs text-brand-muted">
                Add topics from the left panel.
              </p>
            )}

            {sortedClassTopics.map((t, idx) => (
              <div
                key={t.id}
                className="flex items-center gap-1.5 px-2 py-2 rounded-lg border border-role-teacher-border bg-white"
              >
                <span className="w-5 text-center text-[10px] font-bold text-brand-muted flex-shrink-0">
                  {idx + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-brand-ink truncate">
                    {t.topic_name}
                  </p>
                  <p className="text-[10px] text-brand-muted">
                    {t.subtopic_count} subtopic
                    {t.subtopic_count !== 1 ? "s" : ""}
                  </p>
                </div>
                <div className="flex flex-col gap-0.5 flex-shrink-0">
                  <button
                    type="button"
                    disabled={idx === 0 || reorderTopics.isPending}
                    onClick={() => handleMove(idx, "up")}
                    aria-label={`Move ${t.topic_name} up`}
                    className="w-5 h-5 flex items-center justify-center rounded hover:bg-gray-100 disabled:opacity-30 transition-colors"
                  >
                    <ChevronUp className="w-3 h-3" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    disabled={
                      idx === sortedClassTopics.length - 1 ||
                      reorderTopics.isPending
                    }
                    onClick={() => handleMove(idx, "down")}
                    aria-label={`Move ${t.topic_name} down`}
                    className="w-5 h-5 flex items-center justify-center rounded hover:bg-gray-100 disabled:opacity-30 transition-colors"
                  >
                    <ChevronDown className="w-3 h-3" aria-hidden="true" />
                  </button>
                </div>
                <button
                  type="button"
                  disabled={mutating === t.id}
                  onClick={() => handleRemove(t.id)}
                  aria-label={`Remove ${t.topic_name}`}
                  className="flex-shrink-0 w-6 h-6 rounded-full text-gray-400 hover:bg-red-50 hover:text-brand-red transition-all flex items-center justify-center disabled:opacity-50"
                >
                  <Minus className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-3 pt-1">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={onNext}
          disabled={sortedClassTopics.length === 0}
          className="flex-1"
        >
          Next: Design Diagnostic →
        </Button>
      </div>
    </div>
  );
}

// ── Step 2: Diagnostic builder ────────────────────────────────────────────────

interface Step2Props {
  classId: string;
  classTopics: ClassTopicItem[];
  onBack: () => void;
  onDone: () => void;
}

function DiagnosticBuilderStep({
  classId,
  classTopics,
  onBack,
  onDone,
}: Step2Props) {
  const sortedTopics = useMemo(
    () => [...classTopics].sort((a, b) => a.sequence_order - b.sequence_order),
    [classTopics],
  );

  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(
    () => new Set(sortedTopics.map((t) => t.curriculum_topic_id)),
  );
  const [questionCount, setQuestionCount] = useState(20);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const designDiagnostic = useDesignTier1Diagnostic(classId);

  function toggleTopic(curriculumTopicId: string) {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      if (next.has(curriculumTopicId)) next.delete(curriculumTopicId);
      else next.add(curriculumTopicId);
      return next;
    });
  }

  async function handleSubmit() {
    if (selectedTopicIds.size === 0) {
      setError("Select at least one topic for the diagnostic.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await designDiagnostic.mutateAsync({
        topic_ids: Array.from(selectedTopicIds),
        question_count: questionCount,
      });
      onDone();
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes("422")) {
        setError(
          "Not enough questions in the bank for these topics. Try selecting fewer topics or reducing the question count.",
        );
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-brand-body">
        Select which topics to include in the Tier 1 diagnostic and set the
        number of questions. The diagnostic will be created as a{" "}
        <strong>draft</strong> — you can review and publish it from the
        Assessments tab.
      </p>

      {/* Topic selection */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-role-teacher-muted mb-2">
          Topics to assess
          <span className="ml-1.5 font-medium normal-case tracking-normal text-gray-400">
            — {selectedTopicIds.size} of {sortedTopics.length} selected
          </span>
        </p>
        <div className="space-y-1.5 max-h-56 overflow-y-auto border border-role-teacher-border rounded-xl p-2">
          {sortedTopics.map((t) => {
            const checked = selectedTopicIds.has(t.curriculum_topic_id);
            return (
              <label
                key={t.id}
                className={[
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-all",
                  checked
                    ? "bg-brand-green-light border-brand-primary"
                    : "border-role-teacher-border hover:border-brand-primary/40",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleTopic(t.curriculum_topic_id)}
                  className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-primary"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-brand-ink truncate">
                    {t.topic_name}
                  </p>
                  <p className="text-[10px] text-brand-muted">
                    {t.subtopic_count} subtopic
                    {t.subtopic_count !== 1 ? "s" : ""}
                  </p>
                </div>
                {checked && (
                  <Check
                    className="w-4 h-4 text-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                )}
              </label>
            );
          })}
        </div>
      </div>

      {/* Question count */}
      <div>
        <label
          htmlFor="questionCount"
          className="block text-sm font-semibold text-brand-ink mb-1.5"
        >
          Number of questions
        </label>
        <div className="flex items-center gap-3">
          <input
            id="questionCount"
            type="range"
            min={5}
            max={60}
            step={5}
            value={questionCount}
            onChange={(e) => setQuestionCount(Number(e.target.value))}
            className="flex-1 accent-brand-primary"
          />
          <span className="w-10 text-center font-bold text-brand-ink text-sm">
            {questionCount}
          </span>
        </div>
        <p className="text-[10px] text-brand-muted mt-1">
          Questions are sampled from the bank across all selected topics.
        </p>
      </div>

      {error && (
        <div className="text-xs text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-1">
        <Button type="button" variant="secondary" onClick={onBack}>
          ← Back
        </Button>
        <Button
          type="button"
          variant="primary"
          loading={submitting}
          disabled={submitting || selectedTopicIds.size === 0}
          onClick={handleSubmit}
          className="flex-1"
        >
          Create Draft Diagnostic
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
  const { data: classTopics = [] } = useClassTopics(classId);

  const [done, setDone] = useState(false);

  function handleClose() {
    setStep(initialStep);
    setDone(false);
    onClose();
  }

  const stepTitle =
    step === 1 ? "Step 1 of 2 — Add Topics" : "Step 2 of 2 — Design Diagnostic";

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
        <div className="flex items-center gap-2 mb-5">
          {([1, 2] as const).map((n) => (
            <div key={n} className="flex items-center gap-2">
              <div
                className={[
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0",
                  step === n
                    ? "bg-brand-gold text-white"
                    : n < step
                      ? "bg-brand-primary text-white"
                      : "bg-gray-100 text-gray-400",
                ].join(" ")}
                aria-current={step === n ? "step" : undefined}
              >
                {n < step ? (
                  <Check className="w-3.5 h-3.5" aria-hidden="true" />
                ) : (
                  n
                )}
              </div>
              {n === 1 && (
                <div
                  className={[
                    "h-0.5 w-8 rounded transition-all",
                    step > 1 ? "bg-brand-primary" : "bg-gray-200",
                  ].join(" ")}
                />
              )}
            </div>
          ))}
          <span className="text-xs text-brand-muted ml-1">{stepTitle}</span>
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
              Diagnostic created!
            </h3>
            <p className="text-sm text-brand-body">
              Your draft Tier 1 diagnostic is ready. Go to{" "}
              <strong>Assessments</strong> to review and publish it to students.
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
          <TopicPickerStep
            classId={classId}
            onNext={() => setStep(2)}
            onCancel={handleClose}
          />
        ) : (
          <DiagnosticBuilderStep
            classId={classId}
            classTopics={classTopics}
            onBack={() => setStep(1)}
            onDone={() => setDone(true)}
          />
        )}
      </div>
    </Modal>
  );
}
