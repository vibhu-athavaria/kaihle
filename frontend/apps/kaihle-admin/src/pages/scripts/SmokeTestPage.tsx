import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  ArrowLeft,
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  FlaskConical,
} from "lucide-react";
import {
  useSmokeTestConceptExplanation,
  useSmokeTestMiniCourse,
  useSmokeTestLessonPlan,
  useSmokeTestPracticeQuiz,
  ConceptExplanationResult,
  MiniCourseResult,
  LessonPlanResult,
  PracticeQuizResult,
} from "../../hooks/useAiSmokeTests";

// ---------------------------------------------------------------------------
// Shared field components
// ---------------------------------------------------------------------------

function Field({
  label,
  value,
}: {
  label: string;
  value: string | number | boolean | null | undefined;
}) {
  const display =
    value === null || value === undefined
      ? "—"
      : typeof value === "boolean"
        ? value
          ? "Yes"
          : "No"
        : String(value);
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm text-role-admin-ink break-words">
        {display}
      </dd>
    </div>
  );
}

function TextBlock({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted mb-1">
        {label}
      </p>
      <pre className="text-xs text-role-admin-ink bg-gray-50 border border-role-admin-border rounded-lg p-3 whitespace-pre-wrap leading-relaxed font-['Inter']">
        {text}
      </pre>
    </div>
  );
}

function JsonBlock({ label, data }: { label: string; data: unknown }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted mb-1">
        {label}
      </p>
      <pre className="text-xs text-role-admin-ink bg-gray-50 border border-role-admin-border rounded-lg p-3 whitespace-pre-wrap leading-relaxed font-['Inter'] overflow-auto max-h-80">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function ResultCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 border border-role-admin-border rounded-xl p-5 bg-white space-y-4">
      <h3 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted flex items-center gap-1.5">
        <CheckCircle className="w-3.5 h-3.5 text-brand-primary" />
        Result
      </h3>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4">{children}</dl>
    </div>
  );
}

function ErrorCard({ error }: { error: string }) {
  return (
    <div className="mt-6 border border-red-200 rounded-xl p-5 bg-red-50 flex items-start gap-3">
      <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
      <p className="text-sm text-red-700">{error}</p>
    </div>
  );
}

function Input({
  label,
  required,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  required?: boolean;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-role-admin-muted mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-role-admin-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
      />
    </div>
  );
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-role-admin-muted mb-1">
        {label}
      </label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full border border-role-admin-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-primary"
      />
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 w-4 h-4 rounded border-role-admin-border text-brand-primary focus:ring-brand-primary"
      />
      <span>
        <span className="text-sm text-role-admin-ink">{label}</span>
        {description && (
          <span className="block text-xs text-role-admin-muted">
            {description}
          </span>
        )}
      </span>
    </label>
  );
}

function RunButton({
  onClick,
  loading,
}: {
  onClick: () => void;
  loading: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex items-center gap-2 px-4 py-2 rounded-full bg-brand-primary text-white text-sm font-medium hover:bg-brand-primary/90 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
      ) : (
        <Play className="w-4 h-4" aria-hidden="true" />
      )}
      {loading ? "Running…" : "Run Test"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// 1. Concept Explanation
// ---------------------------------------------------------------------------

function ConceptExplanationTest() {
  const [subtopicId, setSubtopicId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [question, setQuestion] = useState("");
  const mutation = useSmokeTestConceptExplanation();

  const run = () => {
    mutation.mutate({
      subtopic_id: subtopicId.trim(),
      student_id: studentId.trim() || undefined,
      question: question.trim() || undefined,
    });
  };

  const result = mutation.data as ConceptExplanationResult | undefined;

  return (
    <div>
      <div className="space-y-4">
        <Input
          label="Subtopic ID"
          required
          value={subtopicId}
          onChange={setSubtopicId}
          placeholder="UUID of the subtopic"
        />
        <Input
          label="Student ID (optional)"
          value={studentId}
          onChange={setStudentId}
          placeholder="UUID — omit for anonymous"
        />
        <Input
          label="Follow-up question (optional)"
          value={question}
          onChange={setQuestion}
          placeholder="e.g. Can you give a real-world example?"
        />
      </div>

      <div className="mt-5 flex items-center gap-3">
        <RunButton onClick={run} loading={mutation.isPending} />
        {mutation.isError && (
          <span className="text-xs text-red-600">
            {(mutation.error as Error).message}
          </span>
        )}
      </div>

      {result && (
        <div className="mt-6 space-y-4">
          <ResultCard>
            <Field label="Subtopic" value={result.subtopic_name} />
            <Field label="Modality Used" value={result.modality_used} />
            <Field label="Has Profile" value={result.has_profile} />
            <Field label="Duration" value={`${result.duration_ms} ms`} />
          </ResultCard>
          <TextBlock label="Explanation" text={result.explanation} />
          {result.check_question && (
            <JsonBlock
              label="Check Question (MCQ)"
              data={result.check_question}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Mini-Course Generation
// ---------------------------------------------------------------------------

function MiniCourseTest() {
  const [topicId, setTopicId] = useState("");
  const [schoolId, setSchoolId] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const mutation = useSmokeTestMiniCourse();

  const run = () => {
    mutation.mutate({
      topic_id: topicId.trim(),
      school_id: schoolId.trim(),
      dry_run: dryRun,
    });
  };

  const result = mutation.data as MiniCourseResult | undefined;

  return (
    <div>
      <div className="space-y-4">
        <Input
          label="Topic ID"
          required
          value={topicId}
          onChange={setTopicId}
          placeholder="UUID of the topic"
        />
        <Input
          label="School ID"
          required
          value={schoolId}
          onChange={setSchoolId}
          placeholder="UUID of the school"
        />
        <Toggle
          label="Dry run"
          description="Generate LLM content but do not write to DB"
          checked={dryRun}
          onChange={setDryRun}
        />
      </div>

      <div className="mt-5 flex items-center gap-3">
        <RunButton onClick={run} loading={mutation.isPending} />
        {mutation.isError && (
          <span className="text-xs text-red-600">
            {(mutation.error as Error).message}
          </span>
        )}
      </div>

      {result && (
        <div className="mt-6 space-y-4">
          <ResultCard>
            <Field label="Topic" value={result.topic_name ?? "—"} />
            <Field label="Subtopics Found" value={result.subtopics_found} />
            <Field
              label="Subtopics Processed"
              value={result.subtopics_processed}
            />
            <Field
              label="Explanations Written"
              value={result.explanations_written}
            />
            <Field label="Dry Run" value={result.dry_run} />
            <Field label="Duration" value={`${result.duration_ms} ms`} />
          </ResultCard>

          {result.dry_run_results.length > 0 && (
            <div className="space-y-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted">
                Generated Explanations ({result.dry_run_results.length})
              </p>
              {result.dry_run_results.map((r, i) => (
                <div
                  key={i}
                  className="border border-role-admin-border rounded-lg p-4 space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-role-admin-ink">
                      {r.subtopic_name}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-gray-100 text-role-admin-subtle">
                      {r.interest_label}
                    </span>
                  </div>
                  <p className="text-xs text-role-admin-ink leading-relaxed">
                    {r.explanation_text}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Lesson Plan
// ---------------------------------------------------------------------------

function LessonPlanTest() {
  const [classId, setClassId] = useState("");
  const [subtopicIds, setSubtopicIds] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [dryRun, setDryRun] = useState(true);
  const mutation = useSmokeTestLessonPlan();

  const run = () => {
    mutation.mutate({
      class_id: classId.trim(),
      focus_subtopic_ids: subtopicIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      duration_minutes: durationMinutes,
      dry_run: dryRun,
    });
  };

  const result = mutation.data as LessonPlanResult | undefined;

  return (
    <div>
      <div className="space-y-4">
        <Input
          label="Class ID"
          required
          value={classId}
          onChange={setClassId}
          placeholder="UUID of the class"
        />
        <Input
          label="Focus Subtopic IDs (optional, comma-separated)"
          value={subtopicIds}
          onChange={setSubtopicIds}
          placeholder="uuid1, uuid2, uuid3"
        />
        <NumberInput
          label="Duration (minutes)"
          value={durationMinutes}
          onChange={setDurationMinutes}
          min={15}
          max={180}
          step={5}
        />
        <Toggle
          label="Dry run"
          description="Preview plan without creating a DB row"
          checked={dryRun}
          onChange={setDryRun}
        />
      </div>

      <div className="mt-5 flex items-center gap-3">
        <RunButton onClick={run} loading={mutation.isPending} />
        {mutation.isPending && (
          <span className="text-xs text-role-admin-muted">
            LLM generation can take 20–40 s…
          </span>
        )}
        {mutation.isError && (
          <span className="text-xs text-red-600">
            {(mutation.error as Error).message}
          </span>
        )}
      </div>

      {result && (
        <div className="mt-6 space-y-4">
          <ResultCard>
            <Field label="Class" value={result.class_name} />
            <Field label="Subject" value={result.subject_name} />
            <Field label="Grade" value={result.grade_name} />
            <Field label="Students" value={result.student_count} />
            <Field label="Validation Passed" value={result.validation_passed} />
            <Field label="LLM Calls" value={result.llm_calls} />
            <Field label="Duration" value={`${result.duration_ms} ms`} />
          </ResultCard>

          {result.error && <ErrorCard error={result.error} />}

          {Object.keys(result.modality_distribution).length > 0 && (
            <JsonBlock
              label="Modality Distribution"
              data={result.modality_distribution}
            />
          )}

          {result.top_interests.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted mb-1">
                Top Interests
              </p>
              <div className="flex flex-wrap gap-2">
                {result.top_interests.map((interest) => (
                  <span
                    key={interest}
                    className="px-2.5 py-1 rounded-full text-xs bg-gray-100 text-role-admin-subtle"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            </div>
          )}

          {result.generated_plan && (
            <JsonBlock
              label="Generated Plan (parsed)"
              data={result.generated_plan}
            />
          )}

          {result.raw_llm_output && !result.generated_plan && (
            <TextBlock
              label="Raw LLM Output (validation failed)"
              text={result.raw_llm_output.slice(0, 2000)}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Practice Quiz
// ---------------------------------------------------------------------------

function PracticeQuizTest() {
  const [subtopicId, setSubtopicId] = useState("");
  const [masteryScore, setMasteryScore] = useState(0.5);
  const [studentId, setStudentId] = useState("");
  const mutation = useSmokeTestPracticeQuiz();

  const run = () => {
    mutation.mutate({
      subtopic_id: subtopicId.trim(),
      mastery_score: masteryScore,
      student_id: studentId.trim() || undefined,
    });
  };

  const result = mutation.data as PracticeQuizResult | undefined;

  return (
    <div>
      <div className="space-y-4">
        <Input
          label="Subtopic ID"
          required
          value={subtopicId}
          onChange={setSubtopicId}
          placeholder="UUID of the subtopic"
        />
        <NumberInput
          label="Mastery Score (0.0 – 1.0)"
          value={masteryScore}
          onChange={setMasteryScore}
          min={0}
          max={1}
          step={0.05}
        />
        <Input
          label="Student ID (optional)"
          value={studentId}
          onChange={setStudentId}
          placeholder="UUID — omit for no personalisation"
        />
      </div>

      <div className="mt-5 flex items-center gap-3">
        <RunButton onClick={run} loading={mutation.isPending} />
        {mutation.isError && (
          <span className="text-xs text-red-600">
            {(mutation.error as Error).message}
          </span>
        )}
      </div>

      {result && (
        <div className="mt-6 space-y-4">
          <ResultCard>
            <Field label="Subtopic" value={result.subtopic_name} />
            <Field label="Difficulty" value={result.difficulty_label} />
            <Field label="Question Count" value={result.question_count} />
            <Field
              label="Explanation Context Found"
              value={result.explanation_context_found}
            />
            <Field label="Duration" value={`${result.duration_ms} ms`} />
          </ResultCard>

          {!result.explanation_context_found && (
            <div className="flex items-start gap-2 border border-amber-200 rounded-lg p-3 bg-amber-50">
              <span className="text-amber-600 text-xs font-medium">
                ⚠ No approved explanation found for this subtopic. Quiz was
                generated without context personalisation. This may indicate a
                PK mismatch in SubtopicContent lookup.
              </span>
            </div>
          )}

          {result.interests_used.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted mb-1">
                Interests Used
              </p>
              <div className="flex flex-wrap gap-2">
                {result.interests_used.map((i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full text-xs bg-gray-100 text-role-admin-subtle"
                  >
                    {i}
                  </span>
                ))}
              </div>
            </div>
          )}

          {result.questions.length > 0 && (
            <div className="space-y-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-role-admin-muted">
                Questions ({result.questions.length})
              </p>
              {result.questions.map((q, i) => (
                <div
                  key={i}
                  className="border border-role-admin-border rounded-lg p-4 space-y-2"
                >
                  <p className="text-sm font-medium text-role-admin-ink">
                    {i + 1}. {q.question_text}
                  </p>
                  <ul className="space-y-1">
                    {(q.options as Array<{ key: string; text: string }>).map(
                      (opt) => (
                        <li
                          key={opt.key}
                          className={`text-xs px-2 py-1 rounded ${
                            opt.key === q.correct_answer
                              ? "bg-brand-primary/10 text-brand-primary font-medium"
                              : "text-role-admin-subtle"
                          }`}
                        >
                          {opt.key}. {opt.text}
                        </li>
                      ),
                    )}
                  </ul>
                  {q.explanation && (
                    <p className="text-xs text-role-admin-muted italic">
                      {q.explanation}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Test registry
// ---------------------------------------------------------------------------

const SMOKE_TESTS: Record<
  string,
  { title: string; description: string; component: React.ComponentType }
> = {
  "concept-explanation": {
    title: "Concept Explanation",
    description:
      "Generate a personalised subtopic explanation with optional MCQ check question. Uses the student's dominant learning modality if a profile exists.",
    component: ConceptExplanationTest,
  },
  "mini-course": {
    title: "Mini-Course Generation",
    description:
      "Generate interest-personalised explanations for all subtopics in a topic across 4 interest categories. Dry run prevents DB writes.",
    component: MiniCourseTest,
  },
  "lesson-plan": {
    title: "Lesson Plan",
    description:
      "Generate a lesson plan for a class based on student learning profiles. Runs full LLM + validation pipeline without creating any DB row.",
    component: LessonPlanTest,
  },
  "practice-quiz": {
    title: "Practice Quiz",
    description:
      "Generate a practice quiz at a given mastery level. Also checks whether an approved explanation context was found for the subtopic.",
    component: PracticeQuizTest,
  },
};

// ---------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------

export function SmokeTestPage() {
  const { testName } = useParams<{ testName: string }>();
  const { logout } = useAuth();

  const test = testName ? SMOKE_TESTS[testName] : undefined;

  if (!test) {
    return (
      <AdminLayout pageTitle="AI Smoke Tests" onLogout={logout}>
        <div className="p-6">
          <Link
            to="/kaihle-admin/scripts"
            className="inline-flex items-center gap-1.5 text-xs text-role-admin-subtle hover:text-role-admin-ink mb-6"
          >
            <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            Back to Scripts
          </Link>
          <div className="text-center py-16">
            <XCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-sm text-role-admin-muted">
              Smoke test "{testName}" not found.
            </p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  const TestComponent = test.component;

  return (
    <AdminLayout pageTitle={`Smoke Test — ${test.title}`} onLogout={logout}>
      <div className="p-6 max-w-2xl">
        <Link
          to="/kaihle-admin/scripts"
          className="inline-flex items-center gap-1.5 text-xs text-role-admin-subtle hover:text-role-admin-ink mb-6"
        >
          <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
          Back to Scripts
        </Link>

        <div className="flex items-start gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
            <FlaskConical
              className="w-5 h-5 text-brand-primary"
              aria-hidden="true"
            />
          </div>
          <div>
            <h1 className="text-sm font-bold text-role-admin-ink">
              {test.title}
            </h1>
            <p className="text-xs text-role-admin-subtle mt-0.5">
              {test.description}
            </p>
          </div>
        </div>

        <div className="border border-role-admin-border rounded-xl p-5 bg-white">
          <TestComponent />
        </div>
      </div>
    </AdminLayout>
  );
}
