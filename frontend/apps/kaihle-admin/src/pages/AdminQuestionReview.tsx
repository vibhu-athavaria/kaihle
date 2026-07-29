import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { Pencil, Plus, Trash2 } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface McqOption {
  key: string;
  text: string;
}

interface QuestionRow {
  id: string;
  question_text: string;
  question_type: "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER";
  options: McqOption[] | null;
  correct_answer: string;
  explanation: string | null;
  difficulty_level: number | null;
  is_active: boolean;
  meta_tags: Record<string, unknown> | null;
  source: string | null;
  replaces_question_id: string | null;
  subtopic_id: string | null;
  curriculum_id: string | null;
  curriculum_name: string | null;
  subject_id: string | null;
  subject_name: string | null;
  grade_id: string | null;
  grade_name: string | null;
  topic_id: string | null;
  topic_name: string | null;
  subtopic_name: string | null;
  curriculum_topic_id: string | null;
}

interface QuestionListResponse {
  questions: QuestionRow[];
  total: number;
  page: number;
  page_size: number;
}

interface FilterOption {
  id: string;
  name: string;
}

const QUESTION_TYPES = ["MCQ", "TRUE_FALSE", "SHORT_ANSWER"] as const;
const MCQ_KEYS = ["A", "B", "C", "D"];

const TYPE_PILL: Record<string, string> = {
  MCQ: "bg-blue-50 text-blue-700",
  TRUE_FALSE: "bg-purple-50 text-purple-700",
  SHORT_ANSWER: "bg-amber-50 text-amber-700",
};

function difficultyLabel(val: number | null) {
  if (val === null) return { label: "—", cls: "text-[#9ca3af]" };
  if (val >= 4.0) return { label: "Hard", cls: "text-[#ef4444]" };
  if (val >= 2.5) return { label: "Med", cls: "text-[#f59e0b]" };
  return { label: "Easy", cls: "text-[#16a34a]" };
}

// ── Shared filter selects ──────────────────────────────────────────────────

const selectCls =
  "border border-[#eaecf0] rounded-md text-xs text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]";

// ── Main page ──────────────────────────────────────────────────────────────

export function AdminQuestionReview() {
  const { logout } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const curriculumId = searchParams.get("curriculum_id") ?? "";
  const gradeId = searchParams.get("grade_id") ?? "";
  const subjectId = searchParams.get("subject_id") ?? "";
  const topicId = searchParams.get("topic_id") ?? "";
  const subtopicId = searchParams.get("subtopic_id") ?? "";
  const curriculumTopicId = searchParams.get("curriculum_topic_id") ?? "";
  const questionType = searchParams.get("question_type") ?? "";
  const search = searchParams.get("search") ?? "";
  const statusFilter = searchParams.get("status") ?? "";
  const page = parseInt(searchParams.get("page") ?? "1", 10);

  const { data: curriculaData } = useQuery({
    queryKey: ["curricula"],
    queryFn: () =>
      apiClient.get<FilterOption[]>("/api/v1/curricula").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });
  const { data: gradesData } = useQuery({
    queryKey: ["grades"],
    queryFn: () =>
      apiClient.get<FilterOption[]>("/api/v1/grades").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });
  const { data: subjectsData } = useQuery({
    queryKey: ["subjects"],
    queryFn: () =>
      apiClient.get<FilterOption[]>("/api/v1/subjects").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });
  const { data: topicsData } = useQuery({
    queryKey: ["topics"],
    queryFn: () =>
      apiClient.get<FilterOption[]>("/api/v1/topics").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });
  const { data: subtopicsData } = useQuery({
    queryKey: ["subtopics"],
    queryFn: () =>
      apiClient.get<FilterOption[]>("/api/v1/subtopics").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });
  const { data: curriculumTopicsData } = useQuery({
    queryKey: ["curriculum-topics"],
    queryFn: () =>
      apiClient
        .get<FilterOption[]>("/api/v1/curriculum-topics")
        .then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const curriculums = curriculaData ?? [];
  const grades = gradesData ?? [];
  const subjects = subjectsData ?? [];
  const topics = topicsData ?? [];
  const subtopics = subtopicsData ?? [];
  const curriculumTopics = curriculumTopicsData ?? [];

  const [data, setData] = useState<QuestionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingQuestion, setEditingQuestion] = useState<QuestionRow | null>(
    null,
  );
  const [addingQuestion, setAddingQuestion] = useState(false);
  const [reviewingCorrection, setReviewingCorrection] =
    useState<QuestionRow | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number | boolean> = {
      page,
      page_size: 20,
    };
    if (curriculumId) params.curriculum_id = curriculumId;
    if (gradeId) params.grade_id = gradeId;
    if (subjectId) params.subject_id = subjectId;
    if (topicId) params.topic_id = topicId;
    if (subtopicId) params.subtopic_id = subtopicId;
    if (curriculumTopicId) params.curriculum_topic_id = curriculumTopicId;
    if (questionType) params.question_type = questionType;
    if (search) params.search = search;
    if (statusFilter === "inactive") params.is_active = false;
    if (statusFilter === "pending") params.source = "llm-correction";
    if (statusFilter === "pending") params.is_active = false;
    if (statusFilter === "pending") params.has_replaces = true;

    apiClient
      .get("/api/v1/question-bank", { params })
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [
    curriculumId,
    gradeId,
    subjectId,
    topicId,
    subtopicId,
    curriculumTopicId,
    questionType,
    search,
    statusFilter,
    page,
    refreshKey,
  ]);

  const setFilter = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      // Reset to page 1 only when a filter (not page) changes
      if (key !== "page") {
        next.delete("page");
      }
      setSearchParams(next);
    },
    [searchParams, setSearchParams],
  );

  const clearAll = useCallback(() => {
    setSearchParams(new URLSearchParams());
  }, [setSearchParams]);

  const handleSaved = (updated: QuestionRow) => {
    setData((prev) =>
      prev
        ? {
            ...prev,
            questions: prev.questions.map((q) =>
              q.id === updated.id ? updated : q,
            ),
          }
        : prev,
    );
    setEditingQuestion(null);
    queryClient.invalidateQueries({ queryKey: ["question-bank"] });
  };

  const handleCreated = (created: QuestionRow) => {
    setData((prev) =>
      prev
        ? {
            ...prev,
            questions: [created, ...prev.questions],
            total: prev.total + 1,
          }
        : prev,
    );
    setAddingQuestion(false);
    queryClient.invalidateQueries({ queryKey: ["question-bank"] });
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;
  const startItem = data ? (page - 1) * data.page_size + 1 : 0;
  const endItem = data ? Math.min(page * data.page_size, data.total) : 0;

  return (
    <AdminLayout pageTitle="Assessment Questions" onLogout={logout}>
      {/* Filter bar */}
      <div className="bg-white border border-[#eaecf0] rounded-lg p-3 mb-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          <select
            className={`${selectCls} w-36`}
            value={curriculumId}
            onChange={(e) => setFilter("curriculum_id", e.target.value)}
          >
            <option value="">Curriculum</option>
            {curriculums.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-28`}
            value={gradeId}
            onChange={(e) => setFilter("grade_id", e.target.value)}
          >
            <option value="">Grade</option>
            {grades.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-32`}
            value={subjectId}
            onChange={(e) => setFilter("subject_id", e.target.value)}
          >
            <option value="">Subject</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-36`}
            value={topicId}
            onChange={(e) => setFilter("topic_id", e.target.value)}
          >
            <option value="">Topic</option>
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-36`}
            value={subtopicId}
            onChange={(e) => setFilter("subtopic_id", e.target.value)}
          >
            <option value="">Subtopic</option>
            {subtopics.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-40`}
            value={curriculumTopicId}
            onChange={(e) => setFilter("curriculum_topic_id", e.target.value)}
          >
            <option value="">Curr. Topic</option>
            {curriculumTopics.map((ct) => (
              <option key={ct.id} value={ct.id}>
                {ct.name}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-32`}
            value={questionType}
            onChange={(e) => setFilter("question_type", e.target.value)}
          >
            <option value="">Type</option>
            {QUESTION_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            className={`${selectCls} w-40`}
            value={statusFilter}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="pending">Pending Corrections</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="🔍 Search question text…"
            className={`${selectCls} flex-1`}
            value={search}
            onChange={(e) => setFilter("search", e.target.value)}
          />
          <button
            onClick={clearAll}
            className="text-xs font-semibold text-[#6b7280] hover:text-[#374151] px-2 py-1"
          >
            Clear all
          </button>
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white border border-[#eaecf0] rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#eaecf0]">
          <h2 className="text-xs font-semibold text-[#374151]">
            Assessment Questions
          </h2>
          <div className="flex items-center gap-3">
            {data && (
              <span className="text-xs text-[#6b7280]">
                Showing {startItem}–{endItem} of {data.total} questions
              </span>
            )}
            <button
              onClick={() => setAddingQuestion(true)}
              className="flex items-center gap-1.5 bg-[#1a5c38] text-white text-xs font-semibold px-3 py-1.5 rounded-full hover:bg-[#155231] transition-colors"
            >
              <Plus className="w-3.5 h-3.5" aria-hidden="true" />
              Add Question
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#eaecf0]">
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Question
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Type
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Curr.
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Gr
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Subj
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Topic
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Subtopic
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Diff
                </th>
                <th className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider text-[#9ca3af]">
                  Edit
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i} className="border-b border-[#eaecf0]">
                    <td colSpan={9} className="py-3 px-3">
                      <div className="h-4 bg-gray-100 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : data && data.questions.length > 0 ? (
                data.questions.map((q) => {
                  const diff = difficultyLabel(q.difficulty_level);
                  return (
                    <tr
                      key={q.id}
                      className="border-b border-[#eaecf0] hover:bg-[#fafafa] transition-colors"
                    >
                      <td className="py-2 px-3 text-xs text-[#374151] max-w-xs truncate">
                        {q.source === "llm-correction" && (
                          <span className="inline-block bg-orange-50 text-orange-700 text-[10px] font-bold uppercase px-1 py-0.5 rounded mr-1.5 align-middle">
                            Correction
                          </span>
                        )}
                        {q.question_text.slice(0, 80)}
                        {q.question_text.length > 80 ? "…" : ""}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                            TYPE_PILL[q.question_type] ||
                            "bg-gray-50 text-gray-600"
                          }`}
                        >
                          {q.question_type}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-xs text-[#374151]">
                        {q.curriculum_name?.slice(0, 8) ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-xs text-[#374151]">
                        {q.grade_name?.replace("Grade ", "") ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-xs text-[#374151]">
                        {q.subject_name?.slice(0, 6) ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-xs text-[#374151]">
                        {q.topic_name?.slice(0, 10) ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-xs text-[#374151]">
                        {q.subtopic_name?.slice(0, 10) ?? "—"}
                      </td>
                      <td
                        className={`py-2 px-3 text-xs font-medium ${diff.cls}`}
                      >
                        {diff.label}
                      </td>
                      <td className="py-2 px-3">
                        {q.source === "llm-correction" ? (
                          <button
                            onClick={() => setReviewingCorrection(q)}
                            className="text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200 px-2 py-1 rounded hover:bg-orange-100 transition-colors"
                            title="Review correction"
                          >
                            Review
                          </button>
                        ) : (
                          <button
                            onClick={() => setEditingQuestion(q)}
                            className="w-7 h-7 rounded border border-[#eaecf0] bg-white text-[#6b7280] hover:bg-[#f3f4f6] flex items-center justify-center"
                            title="Edit"
                            aria-label="Edit question"
                          >
                            <Pencil
                              className="w-3.5 h-3.5"
                              aria-hidden="true"
                            />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td
                    colSpan={9}
                    className="py-12 text-center text-xs text-[#9ca3af]"
                  >
                    No questions found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-1 py-3 border-t border-[#eaecf0]">
            <button
              onClick={() => setFilter("page", String(page - 1))}
              disabled={page <= 1}
              className="w-8 h-8 rounded border border-[#eaecf0] bg-white text-[#374151] text-xs font-semibold hover:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ←
            </button>
            {[...Array(Math.min(5, totalPages))].map((_, i) => {
              const p = i + Math.max(1, page - 2);
              if (p > totalPages) return null;
              return (
                <button
                  key={p}
                  onClick={() => setFilter("page", String(p))}
                  className={`w-8 h-8 rounded border text-xs font-semibold ${
                    p === page
                      ? "bg-[#1a5c38] border-[#1a5c38] text-white"
                      : "border-[#eaecf0] bg-white text-[#374151] hover:bg-[#f3f4f6]"
                  }`}
                >
                  {p}
                </button>
              );
            })}
            <button
              onClick={() => setFilter("page", String(page + 1))}
              disabled={page >= totalPages}
              className="w-8 h-8 rounded border border-[#eaecf0] bg-white text-[#374151] text-xs font-semibold hover:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              →
            </button>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingQuestion && (
        <QuestionModal
          mode="edit"
          question={editingQuestion}
          curriculums={curriculums}
          grades={grades}
          subjects={subjects}
          topics={topics}
          subtopics={subtopics}
          onClose={() => setEditingQuestion(null)}
          onSave={handleSaved}
        />
      )}

      {/* Add Question Modal */}
      {addingQuestion && (
        <QuestionModal
          mode="add"
          curriculums={curriculums}
          grades={grades}
          subjects={subjects}
          topics={topics}
          subtopics={subtopics}
          onClose={() => setAddingQuestion(false)}
          onSave={handleCreated}
        />
      )}

      {/* Review Correction Modal */}
      {reviewingCorrection && (
        <CorrectionReviewModal
          correction={reviewingCorrection}
          onClose={() => setReviewingCorrection(null)}
          onApprove={() => {
            setReviewingCorrection(null);
            setRefreshKey((k) => k + 1);
          }}
          onReject={() => {
            setReviewingCorrection(null);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </AdminLayout>
  );
}

// ── Question Modal (Edit + Add) ────────────────────────────────────────────

interface QuestionModalProps {
  mode: "edit" | "add";
  question?: QuestionRow;
  curriculums: FilterOption[];
  grades: FilterOption[];
  subjects: FilterOption[];
  topics: FilterOption[];
  subtopics: FilterOption[];
  onClose: () => void;
  onSave: (q: QuestionRow) => void;
}

function buildDefaultOptions(): McqOption[] {
  return MCQ_KEYS.map((key) => ({ key, text: "" }));
}

function QuestionModal({
  mode,
  question,
  curriculums,
  grades,
  subjects,
  topics,
  subtopics,
  onClose,
  onSave,
}: QuestionModalProps) {
  const isEdit = mode === "edit";

  const [form, setForm] = useState({
    question_text: question?.question_text ?? "",
    question_type:
      question?.question_type ??
      ("MCQ" as "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER"),
    correct_answer: question?.correct_answer ?? "",
    explanation: question?.explanation ?? "",
    difficulty_level: question?.difficulty_level ?? ("" as number | ""),
    is_active: question?.is_active ?? true,
  });

  // MCQ options — pre-populate from existing question or start fresh
  const [options, setOptions] = useState<McqOption[]>(() => {
    if (question?.question_type === "MCQ" && question.options?.length) {
      return question.options as McqOption[];
    }
    return buildDefaultOptions();
  });

  // Curriculum context selects — pre-populate with question's current IDs
  const [selectedCurriculum, setSelectedCurriculum] = useState(
    question?.curriculum_id ?? "",
  );
  const [selectedGrade, setSelectedGrade] = useState(question?.grade_id ?? "");
  const [selectedSubject, setSelectedSubject] = useState(
    question?.subject_id ?? "",
  );
  const [selectedTopic, setSelectedTopic] = useState(question?.topic_id ?? "");
  const [selectedSubtopic, setSelectedSubtopic] = useState(
    question?.subtopic_id ?? "",
  );

  const [fetchedSubtopics, setFetchedSubtopics] = useState<FilterOption[]>([]);
  const filteredSubtopics = useMemo(
    () => (selectedTopic ? fetchedSubtopics : subtopics),
    [selectedTopic, fetchedSubtopics, subtopics],
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch subtopics when topic changes
  useEffect(() => {
    if (!selectedTopic) return;
    const controller = new AbortController();
    apiClient
      .get("/api/v1/subtopics", {
        params: { topic_id: selectedTopic },
        signal: controller.signal,
      })
      .then((r) => setFetchedSubtopics(r.data))
      .catch((err) => {
        if (err.name !== "CanceledError") setFetchedSubtopics([]);
      });
    return () => controller.abort();
  }, [selectedTopic]);

  // Reset options when question type changes
  useEffect(() => {
    if (form.question_type === "MCQ" && !options.length) {
      setOptions(buildDefaultOptions());
    }
  }, [form.question_type, options.length]);

  const handleCurriculumChange = (v: string) => {
    setSelectedCurriculum(v);
    setSelectedGrade("");
    setSelectedSubject("");
    setSelectedTopic("");
    setSelectedSubtopic("");
    setFetchedSubtopics([]);
  };
  const handleGradeChange = (v: string) => {
    setSelectedGrade(v);
    setSelectedSubject("");
    setSelectedTopic("");
    setSelectedSubtopic("");
    setFetchedSubtopics([]);
  };
  const handleSubjectChange = (v: string) => {
    setSelectedSubject(v);
    setSelectedTopic("");
    setSelectedSubtopic("");
    setFetchedSubtopics([]);
  };
  const handleTopicChange = (v: string) => {
    setSelectedTopic(v);
    setSelectedSubtopic("");
  };

  const updateOption = (idx: number, text: string) => {
    setOptions((prev) => prev.map((o, i) => (i === idx ? { ...o, text } : o)));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const resolvedOptions = form.question_type === "MCQ" ? options : null;
      const resolvedCorrectAnswer =
        form.question_type === "MCQ"
          ? form.correct_answer
          : form.correct_answer;

      const payload: Record<string, unknown> = {
        question_text: form.question_text,
        question_type: form.question_type,
        options: resolvedOptions,
        correct_answer: resolvedCorrectAnswer,
        explanation: form.explanation || null,
        difficulty_level:
          form.difficulty_level !== ""
            ? parseFloat(String(form.difficulty_level))
            : null,
        is_active: form.is_active,
      };

      if (isEdit) {
        // Only send subtopic_id if admin actually changed it
        if (
          selectedSubtopic &&
          selectedSubtopic !== (question?.subtopic_id ?? "")
        ) {
          payload.subtopic_id = selectedSubtopic;
        }
        const resp = await apiClient.patch(
          `/api/v1/question-bank/${question!.id}`,
          payload,
        );
        onSave(resp.data);
      } else {
        // Create — subtopic is required
        if (!selectedSubtopic) {
          setError("Please select a subtopic to assign this question.");
          setSaving(false);
          return;
        }
        payload.subtopic_id = selectedSubtopic;
        const resp = await apiClient.post("/api/v1/question-bank", payload);
        onSave(resp.data);
      }
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "Failed to save. Please try again.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const isFormValid =
    form.question_text.trim() &&
    form.question_type &&
    (form.question_type !== "MCQ" ||
      (options.every((o) => o.text.trim()) && form.correct_answer.trim())) &&
    (form.question_type === "MCQ" || form.correct_answer.trim()) &&
    (isEdit || selectedSubtopic);

  const currentContext = isEdit
    ? [
        question?.curriculum_name,
        question?.grade_name,
        question?.subject_name,
        question?.topic_name,
        question?.subtopic_name,
      ]
        .filter(Boolean)
        .join(" → ")
    : null;

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-lg w-full max-w-[840px] shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#eaecf0] flex items-center justify-between flex-shrink-0">
          <h2 className="text-sm font-semibold text-[#111827]">
            {isEdit ? "Edit Question" : "Add New Question"}
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded hover:bg-[#f3f4f6] flex items-center justify-center text-[#6b7280]"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-6 py-5 space-y-5 flex-1">
          {/* Curriculum Context */}
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3">
              CURRICULUM CONTEXT
              {isEdit && (
                <span className="ml-2 normal-case font-normal text-[#9ca3af]">
                  — change subtopic to reassign
                </span>
              )}
            </div>
            {isEdit && currentContext && (
              <p className="text-xs text-[#6b7280] mb-2">
                Current:{" "}
                <span className="text-[#374151]">{currentContext}</span>
              </p>
            )}
            <div className="grid grid-cols-5 gap-2">
              <div>
                <label className="text-[10px] text-[#9ca3af] font-semibold uppercase tracking-wide mb-1 block">
                  Curriculum
                </label>
                <select
                  className={`${selectCls} w-full`}
                  value={selectedCurriculum}
                  onChange={(e) => handleCurriculumChange(e.target.value)}
                >
                  <option value="">{isEdit ? "Unchanged" : "Select…"}</option>
                  {curriculums.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#9ca3af] font-semibold uppercase tracking-wide mb-1 block">
                  Grade
                </label>
                <select
                  className={`${selectCls} w-full`}
                  value={selectedGrade}
                  onChange={(e) => handleGradeChange(e.target.value)}
                >
                  <option value="">{isEdit ? "Unchanged" : "Select…"}</option>
                  {grades.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#9ca3af] font-semibold uppercase tracking-wide mb-1 block">
                  Subject
                </label>
                <select
                  className={`${selectCls} w-full`}
                  value={selectedSubject}
                  onChange={(e) => handleSubjectChange(e.target.value)}
                >
                  <option value="">{isEdit ? "Unchanged" : "Select…"}</option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#9ca3af] font-semibold uppercase tracking-wide mb-1 block">
                  Topic
                </label>
                <select
                  className={`${selectCls} w-full`}
                  value={selectedTopic}
                  onChange={(e) => handleTopicChange(e.target.value)}
                >
                  <option value="">{isEdit ? "Unchanged" : "Select…"}</option>
                  {topics.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#9ca3af] font-semibold uppercase tracking-wide mb-1 block">
                  Subtopic{" "}
                  {!isEdit && <span className="text-[#ef4444]">*</span>}
                </label>
                <select
                  className={`${selectCls} w-full`}
                  value={selectedSubtopic}
                  onChange={(e) => setSelectedSubtopic(e.target.value)}
                >
                  <option value="">{isEdit ? "Unchanged" : "Select…"}</option>
                  {filteredSubtopics.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Content */}
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3">
              CONTENT
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-[#374151] font-medium mb-1 block">
                  Question Text <span className="text-[#ef4444]">*</span>
                </label>
                <textarea
                  className={`${selectCls} w-full resize-none`}
                  rows={4}
                  value={form.question_text}
                  onChange={(e) =>
                    setForm({ ...form, question_text: e.target.value })
                  }
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-[#374151] font-medium mb-1 block">
                    Question Type <span className="text-[#ef4444]">*</span>
                  </label>
                  <select
                    className={`${selectCls} w-full`}
                    value={form.question_type}
                    onChange={(e) => {
                      const qt = e.target.value as
                        | "MCQ"
                        | "TRUE_FALSE"
                        | "SHORT_ANSWER";
                      setForm({
                        ...form,
                        question_type: qt,
                        correct_answer: "",
                      });
                      if (qt === "MCQ") setOptions(buildDefaultOptions());
                    }}
                  >
                    {QUESTION_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-[#374151] font-medium mb-1 block">
                    Difficulty (1.0–5.0)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="5"
                    step="0.1"
                    className={`${selectCls} w-full`}
                    value={form.difficulty_level}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        difficulty_level: e.target.value as unknown as
                          | number
                          | "",
                      })
                    }
                  />
                </div>
              </div>

              {/* MCQ Options */}
              {form.question_type === "MCQ" && (
                <div>
                  <label className="text-xs text-[#374151] font-medium mb-2 block">
                    Answer Options <span className="text-[#ef4444]">*</span>
                  </label>
                  <div className="space-y-2">
                    {options.map((opt, idx) => (
                      <div key={opt.key} className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-[#f3f4f6] border border-[#eaecf0] flex items-center justify-center text-xs font-bold text-[#374151] flex-shrink-0">
                          {opt.key}
                        </span>
                        <input
                          type="text"
                          className={`${selectCls} flex-1`}
                          placeholder={`Option ${opt.key}`}
                          value={opt.text}
                          onChange={(e) => updateOption(idx, e.target.value)}
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setForm({ ...form, correct_answer: opt.key })
                          }
                          className={`text-xs px-2 py-1 rounded border transition-colors ${
                            form.correct_answer === opt.key
                              ? "bg-[#1a5c38] border-[#1a5c38] text-white font-semibold"
                              : "border-[#eaecf0] text-[#6b7280] hover:border-[#1a5c38] hover:text-[#1a5c38]"
                          }`}
                          title={`Mark ${opt.key} as correct`}
                        >
                          ✓ Correct
                        </button>
                      </div>
                    ))}
                  </div>
                  {form.correct_answer && (
                    <p className="text-xs text-[#1a5c38] font-medium mt-1.5">
                      Correct answer: Option {form.correct_answer}
                    </p>
                  )}
                </div>
              )}

              {/* TRUE_FALSE correct answer */}
              {form.question_type === "TRUE_FALSE" && (
                <div>
                  <label className="text-xs text-[#374151] font-medium mb-1 block">
                    Correct Answer <span className="text-[#ef4444]">*</span>
                  </label>
                  <div className="flex gap-2">
                    {["true", "false"].map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => setForm({ ...form, correct_answer: v })}
                        className={`text-xs px-4 py-2 rounded border capitalize transition-colors ${
                          form.correct_answer === v
                            ? "bg-[#1a5c38] border-[#1a5c38] text-white font-semibold"
                            : "border-[#eaecf0] text-[#374151] hover:border-[#1a5c38]"
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* SHORT_ANSWER correct answer */}
              {form.question_type === "SHORT_ANSWER" && (
                <div>
                  <label className="text-xs text-[#374151] font-medium mb-1 block">
                    Model Answer <span className="text-[#ef4444]">*</span>
                  </label>
                  <textarea
                    className={`${selectCls} w-full resize-none`}
                    rows={2}
                    value={form.correct_answer}
                    onChange={(e) =>
                      setForm({ ...form, correct_answer: e.target.value })
                    }
                  />
                </div>
              )}

              <div>
                <label className="text-xs text-[#374151] font-medium mb-1 block">
                  Explanation
                </label>
                <textarea
                  className={`${selectCls} w-full resize-none`}
                  rows={3}
                  value={form.explanation}
                  onChange={(e) =>
                    setForm({ ...form, explanation: e.target.value })
                  }
                />
              </div>

              <div className="flex items-center gap-3">
                <label className="text-xs text-[#374151] font-medium">
                  Active
                </label>
                <button
                  type="button"
                  role="switch"
                  aria-checked={form.is_active}
                  onClick={() =>
                    setForm({ ...form, is_active: !form.is_active })
                  }
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    form.is_active ? "bg-[#1a5c38]" : "bg-[#e5e7eb]"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      form.is_active ? "translate-x-[18px]" : "translate-x-0.5"
                    }`}
                  />
                </button>
                <span className="text-xs text-[#6b7280]">
                  {form.is_active
                    ? "Visible to assessments"
                    : "Hidden from assessments"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[#eaecf0] px-6 py-4 flex justify-end items-center gap-3 flex-shrink-0">
          {error && (
            <span
              role="alert"
              className="text-xs text-[#ef4444] text-right mr-auto"
            >
              {error}
            </span>
          )}
          <button
            onClick={onClose}
            className="border border-[#eaecf0] bg-white text-[#374151] text-xs font-semibold px-4 py-2 rounded-md hover:bg-[#f3f4f6]"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !isFormValid}
            className="bg-[#1a5c38] text-white text-xs font-semibold px-4 py-2 rounded-md hover:bg-[#155231] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {saving
              ? isEdit
                ? "Saving…"
                : "Adding…"
              : isEdit
                ? "Save changes"
                : "Add question"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Correction Review Modal ─────────────────────────────────────────────────

interface CorrectionReviewModalProps {
  correction: QuestionRow;
  onClose: () => void;
  onApprove: () => void;
  onReject: () => void;
}

function CorrectionReviewModal({
  correction,
  onClose,
  onApprove,
  onReject,
}: CorrectionReviewModalProps) {
  const [original, setOriginal] = useState<QuestionRow | null>(null);
  const [loading, setLoading] = useState(!!correction.replaces_question_id);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Meta data from the correction record
  const metaTags = correction.meta_tags as
    | {
        changes_made?: string[];
        validations?: Record<string, { pass: boolean; note: string }>;
        original?: {
          question_text?: string;
          correct_answer?: string;
          difficulty_level?: number;
          question_type?: string;
          options?: McqOption[];
        };
      }
    | undefined;

  // Fetch original question if we have replaces_question_id
  useEffect(() => {
    if (!correction.replaces_question_id) {
      setLoading(false);
      return;
    }
    apiClient
      .get(`/api/v1/question-bank/${correction.replaces_question_id}`)
      .then((r) => setOriginal(r.data))
      .catch(() => setOriginal(null))
      .finally(() => setLoading(false));
  }, [correction.replaces_question_id]);

  const handleApprove = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await apiClient.post(`/api/v1/question-bank/${correction.id}/approve`);
      onApprove();
    } catch (e: unknown) {
      const msg =
        e instanceof Error
          ? e.message
          : "Failed to approve correction. Please try again.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await apiClient.patch(`/api/v1/question-bank/${correction.id}`, {
        is_active: false,
      });
      onReject();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to reject correction");
    } finally {
      setActionLoading(false);
    }
  };

  const diff = difficultyLabel(correction.difficulty_level);

  const leftQuestion = original || {
    question_text: metaTags?.original?.question_text || "",
    correct_answer: metaTags?.original?.correct_answer || "",
    difficulty_level: metaTags?.original?.difficulty_level ?? null,
    question_type:
      metaTags?.original?.question_type || correction.question_type,
    options: (metaTags?.original?.options as McqOption[]) || null,
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-lg w-full max-w-[960px] shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#eaecf0] flex items-center justify-between flex-shrink-0">
          <h2 className="text-sm font-semibold text-[#111827] flex items-center gap-2">
            <span className="bg-orange-50 text-orange-700 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded">
              Correction
            </span>
            Review Correction
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded hover:bg-[#f3f4f6] flex items-center justify-center text-[#6b7280]"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-6 py-5 flex-1 space-y-5">
          {loading && (
            <div className="text-center py-8 text-xs text-[#9ca3af]">
              Loading original question…
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="text-xs text-[#ef4444] bg-red-50 border border-red-200 rounded-md px-3 py-2"
            >
              {error}
            </div>
          )}

          {!loading && (
            <>
              {/* Side-by-side comparison */}
              <div className="grid grid-cols-2 gap-4">
                {/* Original Question */}
                <div className="border border-[#eaecf0] rounded-lg p-3 bg-[#fafafa]">
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#9ca3af] mb-2">
                    Original
                  </h3>
                  {leftQuestion.question_text ? (
                    <>
                      <p className="text-xs text-[#374151] mb-2 leading-relaxed">
                        {leftQuestion.question_text}
                      </p>
                      {/* MCQ options for original */}
                      {leftQuestion.question_type === "MCQ" &&
                        leftQuestion.options &&
                        leftQuestion.options.length > 0 && (
                          <div className="space-y-1 mb-2">
                            {leftQuestion.options.map((opt) => (
                              <div
                                key={opt.key}
                                className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded ${
                                  opt.key === leftQuestion.correct_answer
                                    ? "bg-green-100 text-[#16a34a] font-semibold"
                                    : "text-[#6b7280]"
                                }`}
                              >
                                <span className="w-5 h-5 rounded-full bg-[#f3f4f6] border border-[#eaecf0] flex items-center justify-center text-[10px] font-bold text-[#374151] flex-shrink-0">
                                  {opt.key}
                                </span>
                                {opt.text}
                              </div>
                            ))}
                          </div>
                        )}
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        <span className="text-[10px] font-semibold text-[#6b7280] bg-gray-100 px-1.5 py-0.5 rounded">
                          Correct: {leftQuestion.correct_answer}
                        </span>
                        <span
                          className={
                            "text-[10px] font-semibold px-1.5 py-0.5 rounded bg-gray-50 " +
                            difficultyLabel(leftQuestion.difficulty_level).cls
                          }
                        >
                          {difficultyLabel(leftQuestion.difficulty_level).label}{" "}
                          ({leftQuestion.difficulty_level})
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-[#9ca3af] italic">
                      Original not available
                    </p>
                  )}
                </div>

                {/* Corrected Question */}
                <div className="border border-[#1a5c38] rounded-lg p-3 bg-green-50/30">
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a5c38] mb-2">
                    Correction
                  </h3>
                  <p className="text-xs text-[#374151] mb-2 leading-relaxed">
                    {correction.question_text}
                  </p>
                  {/* MCQ options for correction */}
                  {correction.question_type === "MCQ" &&
                    correction.options &&
                    correction.options.length > 0 && (
                      <div className="space-y-1 mb-2">
                        {correction.options.map((opt) => (
                          <div
                            key={opt.key}
                            className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded ${
                              opt.key === correction.correct_answer
                                ? "bg-green-100 text-[#16a34a] font-semibold"
                                : "text-[#6b7280]"
                            }`}
                          >
                            <span className="w-5 h-5 rounded-full bg-[#f3f4f6] border border-[#eaecf0] flex items-center justify-center text-[10px] font-bold text-[#374151] flex-shrink-0">
                              {opt.key}
                            </span>
                            {opt.text}
                          </div>
                        ))}
                      </div>
                    )}
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    <span className="text-[10px] font-semibold text-[#6b7280] bg-gray-100 px-1.5 py-0.5 rounded">
                      Correct: {correction.correct_answer}
                    </span>
                    <span
                      className={
                        "text-[10px] font-semibold px-1.5 py-0.5 rounded bg-gray-50 " +
                        diff.cls
                      }
                    >
                      {diff.label} ({correction.difficulty_level})
                    </span>
                  </div>
                  {correction.explanation && (
                    <p className="text-[10px] text-[#6b7280] italic leading-relaxed">
                      {correction.explanation}
                    </p>
                  )}
                </div>
              </div>

              {/* Validation results */}
              {metaTags?.validations && (
                <div>
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#9ca3af] mb-2">
                    Validation Results
                  </h3>
                  <div className="space-y-1.5">
                    {Object.entries(metaTags.validations).map(([key, val]) => (
                      <div
                        key={key}
                        className={
                          "flex items-start gap-2 text-xs px-3 py-1.5 rounded-md " +
                          (val.pass
                            ? "bg-green-50 text-[#16a34a]"
                            : "bg-red-50 text-[#ef4444]")
                        }
                      >
                        <span className="font-semibold shrink-0 w-28 capitalize">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="text-[#374151]">{val.note}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Changes made */}
              {metaTags?.changes_made && metaTags.changes_made.length > 0 && (
                <div>
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#9ca3af] mb-2">
                    Changes Made
                  </h3>
                  <ul className="list-disc list-inside space-y-1">
                    {metaTags.changes_made.map(
                      (change: string, idx: number) => (
                        <li
                          key={idx}
                          className="text-xs text-[#374151] leading-relaxed"
                        >
                          {change}
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              )}

              {/* Replaces info */}
              {correction.replaces_question_id && (
                <div className="bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
                  <p className="text-[10px] text-blue-700">
                    This correction replaces question{" "}
                    <span className="font-mono font-semibold">
                      {correction.replaces_question_id.slice(0, 8)}…
                    </span>
                    . Approving will deactivate the original and activate this
                    correction.
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-[#eaecf0] px-6 py-4 flex justify-end items-center gap-3 flex-shrink-0">
          <button
            onClick={onClose}
            className="border border-[#eaecf0] bg-white text-[#374151] text-xs font-semibold px-4 py-2 rounded-md hover:bg-[#f3f4f6]"
          >
            Cancel
          </button>
          <button
            onClick={handleReject}
            disabled={actionLoading}
            className="flex items-center gap-1.5 border border-[#ef4444] bg-white text-[#ef4444] text-xs font-semibold px-4 py-2 rounded-md hover:bg-red-50 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
            {actionLoading ? "Rejecting…" : "Reject"}
          </button>
          <button
            onClick={handleApprove}
            disabled={actionLoading}
            className="bg-[#1a5c38] text-white text-xs font-semibold px-4 py-2 rounded-md hover:bg-[#155231] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {actionLoading ? "Approving…" : "Approve & Publish"}
          </button>
        </div>
      </div>
    </div>
  );
}
