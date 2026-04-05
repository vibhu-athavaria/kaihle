import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { Pencil } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface QuestionRow {
  id: string;
  question_text: string;
  question_type: "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER";
  correct_answer: string;
  explanation: string | null;
  difficulty_level: number | null;
  is_active: boolean;
  curriculum_name: string | null;
  subject_name: string | null;
  grade_name: string | null;
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

// ── Main page ──────────────────────────────────────────────────────────────

export function AdminQuestionReview() {
  const { logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const curriculumId = searchParams.get("curriculum_id") ?? "";
  const gradeId = searchParams.get("grade_id") ?? "";
  const subjectId = searchParams.get("subject_id") ?? "";
  const topicId = searchParams.get("topic_id") ?? "";
  const subtopicId = searchParams.get("subtopic_id") ?? "";
  const curriculumTopicId = searchParams.get("curriculum_topic_id") ?? "";
  const questionType = searchParams.get("question_type") ?? "";
  const search = searchParams.get("search") ?? "";
  const page = parseInt(searchParams.get("page") ?? "1", 10);

  // React Query hooks for dropdown data with caching
  const { data: curriculaData } = useQuery({
    queryKey: ["curricula"],
    queryFn: () =>
      apiClient.get<FilterOption[]>("/api/v1/curricula").then((r) => r.data),
    staleTime: 5 * 60 * 1000, // 5 minutes
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

  // Use React Query data or fall back to state
  const curriculums = curriculaData ?? [];
  const grades = gradesData ?? [];
  const subjects = subjectsData ?? [];
  const topics = topicsData ?? [];
  const subtopics = subtopicsData ?? [];
  const curriculumTopics = curriculumTopicsData ?? [];

  const [data, setData] = useState<QuestionListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<QuestionRow | null>(
    null,
  );

  // Load question list
  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: 20 };
    if (curriculumId) params.curriculum_id = curriculumId;
    if (gradeId) params.grade_id = gradeId;
    if (subjectId) params.subject_id = subjectId;
    if (topicId) params.topic_id = topicId;
    if (subtopicId) params.subtopic_id = subtopicId;
    if (curriculumTopicId) params.curriculum_topic_id = curriculumTopicId;
    if (questionType) params.question_type = questionType;
    if (search) params.search = search;

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
    page,
  ]);

  const setFilter = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      next.delete("page"); // reset to page 1
      setSearchParams(next);
    },
    [searchParams, setSearchParams],
  );

  const clearAll = useCallback(() => {
    setSearchParams(new URLSearchParams());
  }, [setSearchParams]);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;
  const startItem = data ? (page - 1) * data.page_size + 1 : 0;
  const endItem = data ? Math.min(page * data.page_size, data.total) : 0;

  return (
    <AdminLayout pageTitle="Assessment Questions" onLogout={logout}>
      {/* Filter bar */}
      <div className="bg-white border border-[#eaecf0] rounded-lg p-3 mb-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          <select
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-36"
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
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-28"
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
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-32"
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
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-36"
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
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-36"
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
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-40"
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
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-32"
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
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="🔍 Search question text…"
            className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] flex-1"
            value={search}
            onChange={(e) => setFilter("search", e.target.value)}
          />
          <button
            onClick={clearAll}
            className="text-[11px] font-semibold text-[#6b7280] hover:text-[#374151] px-2 py-1"
          >
            Clear all
          </button>
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white border border-[#eaecf0] rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#eaecf0]">
          <h2 className="text-[11px] font-semibold text-[#374151]">
            Assessment Questions
          </h2>
          {data && (
            <span className="text-[10px] text-[#6b7280]">
              Showing {startItem}–{endItem} of {data.total} questions
            </span>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#eaecf0]">
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Question
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Type
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Curr.
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Gr
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Subj
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Topic
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Subtopic
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
                  Diff
                </th>
                <th className="text-left py-2 px-3 text-[8px] font-bold uppercase tracking-wider text-[#9ca3af]">
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
                      <td className="py-2 px-3 text-[10px] text-[#374151] max-w-xs truncate">
                        {q.question_text.slice(0, 80)}…
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                            TYPE_PILL[q.question_type] ||
                            "bg-gray-50 text-gray-600"
                          }`}
                        >
                          {q.question_type}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-[10px] text-[#374151]">
                        {q.curriculum_name?.slice(0, 8) ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-[10px] text-[#374151]">
                        {q.grade_name?.replace("Grade ", "") ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-[10px] text-[#374151]">
                        {q.subject_name?.slice(0, 6) ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-[10px] text-[#374151]">
                        {q.topic_name?.slice(0, 10) ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-[10px] text-[#374151]">
                        {q.subtopic_name?.slice(0, 10) ?? "—"}
                      </td>
                      <td
                        className={`py-2 px-3 text-[10px] font-medium ${diff.cls}`}
                      >
                        {diff.label}
                      </td>
                      <td className="py-2 px-3">
                        <button
                          onClick={() => setEditingQuestion(q)}
                          className="w-7 h-7 rounded border border-[#eaecf0] bg-white text-[#6b7280] hover:bg-[#f3f4f6] flex items-center justify-center"
                          title="Edit"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td
                    colSpan={9}
                    className="py-12 text-center text-[12px] text-[#9ca3af]"
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
              className="w-8 h-8 rounded border border-[#eaecf0] bg-white text-[#374151] text-[11px] font-semibold hover:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed"
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
                  className={`w-8 h-8 rounded border text-[11px] font-semibold ${
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
              className="w-8 h-8 rounded border border-[#eaecf0] bg-white text-[#374151] text-[11px] font-semibold hover:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              →
            </button>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingQuestion && (
        <EditModal
          question={editingQuestion}
          curriculums={curriculums}
          grades={grades}
          subjects={subjects}
          topics={topics}
          subtopics={subtopics}
          onClose={() => setEditingQuestion(null)}
          onSave={(updated) => {
            // Optimistic update
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
          }}
        />
      )}
    </AdminLayout>
  );
}

// ── Edit Modal ─────────────────────────────────────────────────────────────

interface EditModalProps {
  question: QuestionRow;
  curriculums: FilterOption[];
  grades: FilterOption[];
  subjects: FilterOption[];
  topics: FilterOption[];
  subtopics: FilterOption[];
  onClose: () => void;
  onSave: (q: QuestionRow) => void;
}

function EditModal({
  question,
  curriculums,
  grades,
  subjects,
  topics,
  subtopics,
  onClose,
  onSave,
}: EditModalProps) {
  const [form, setForm] = useState({
    question_text: question.question_text,
    question_type: question.question_type,
    correct_answer: question.correct_answer,
    explanation: question.explanation ?? "",
    difficulty_level: question.difficulty_level ?? "",
    is_active: question.is_active,
  });
  const [selectedCurriculum, setSelectedCurriculum] = useState("");
  const [selectedGrade, setSelectedGrade] = useState("");
  const [selectedSubject, setSelectedSubject] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("");
  const [selectedSubtopic, setSelectedSubtopic] = useState("");
  const [filteredSubtopics, setFilteredSubtopics] = useState<FilterOption[]>(
    [],
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch filtered subtopics when topic is selected (with AbortController for race condition prevention)
  useEffect(() => {
    const controller = new AbortController();
    if (selectedTopic) {
      apiClient
        .get("/api/v1/subtopics", {
          params: { topic_id: selectedTopic },
          signal: controller.signal,
        })
        .then((r) => setFilteredSubtopics(r.data))
        .catch((err) => {
          if (err.name !== "CanceledError") {
            setFilteredSubtopics([]);
          }
        });
    } else {
      setFilteredSubtopics(subtopics);
    }
    return () => controller.abort();
  }, [selectedTopic, subtopics]);

  const handleCurriculumChange = (v: string) => {
    setSelectedCurriculum(v);
    setSelectedGrade("");
    setSelectedSubject("");
    setSelectedTopic("");
    setSelectedSubtopic("");
  };
  const handleGradeChange = (v: string) => {
    setSelectedGrade(v);
    setSelectedSubject("");
    setSelectedTopic("");
    setSelectedSubtopic("");
  };
  const handleSubjectChange = (v: string) => {
    setSelectedSubject(v);
    setSelectedTopic("");
    setSelectedSubtopic("");
  };
  const handleTopicChange = (v: string) => {
    setSelectedTopic(v);
    setSelectedSubtopic("");
    // Subtopics will be filtered by topic on the backend side
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        question_text: form.question_text,
        question_type: form.question_type,
        correct_answer: form.correct_answer,
        explanation: form.explanation || null,
        difficulty_level:
          form.difficulty_level !== ""
            ? parseFloat(String(form.difficulty_level))
            : null,
        is_active: form.is_active,
      };
      if (selectedSubtopic) {
        payload.subtopic_id = selectedSubtopic;
      }
      const resp = await apiClient.patch(
        `/api/v1/question-bank/${question.id}`,
        payload,
      );
      onSave(resp.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const isFormValid =
    form.question_text && form.question_type && form.correct_answer;
  const currentContext = [
    question.curriculum_name,
    question.grade_name,
    question.subject_name,
    question.topic_name,
    question.subtopic_name,
  ]
    .filter(Boolean)
    .join(" → ");

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-[600px] shadow-xl">
        {/* Header */}
        <div className="px-5 py-4 border-b border-[#eaecf0] flex items-center justify-between">
          <h2 className="text-[13px] font-semibold text-[#111827]">
            Edit Question
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded hover:bg-[#f3f4f6] flex items-center justify-center text-[#6b7280]"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto max-h-[70vh] px-5 py-4 space-y-5">
          {/* Curriculum Context */}
          <div>
            <div className="text-[9px] font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3">
              CURRICULUM CONTEXT
            </div>
            <p className="text-[10px] text-[#6b7280] mb-2">
              Current:{" "}
              <span className="text-[#374151]">{currentContext || "None"}</span>
            </p>
            <div className="grid grid-cols-5 gap-2">
              <select
                className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]"
                value={selectedCurriculum}
                onChange={(e) => handleCurriculumChange(e.target.value)}
              >
                <option value="">Unchanged</option>
                {curriculums.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <select
                className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]"
                value={selectedGrade}
                onChange={(e) => handleGradeChange(e.target.value)}
              >
                <option value="">Unchanged</option>
                {grades.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
              <select
                className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]"
                value={selectedSubject}
                onChange={(e) => handleSubjectChange(e.target.value)}
              >
                <option value="">Unchanged</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <select
                className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]"
                value={selectedTopic}
                onChange={(e) => handleTopicChange(e.target.value)}
              >
                <option value="">Unchanged</option>
                {topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <select
                className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38]"
                value={selectedSubtopic}
                onChange={(e) => setSelectedSubtopic(e.target.value)}
              >
                <option value="">Unchanged</option>
                {filteredSubtopics.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Content */}
          <div>
            <div className="text-[9px] font-bold uppercase tracking-widest text-[#9ca3af] border-b border-[#f3f4f6] pb-1 mb-3">
              CONTENT
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">
                  Question Text <span className="text-[#ef4444]">*</span>
                </label>
                <textarea
                  className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full resize-none"
                  rows={4}
                  value={form.question_text}
                  onChange={(e) =>
                    setForm({ ...form, question_text: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">
                  Question Type <span className="text-[#ef4444]">*</span>
                </label>
                <select
                  className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full"
                  value={form.question_type}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      question_type: e.target.value as
                        | "MCQ"
                        | "TRUE_FALSE"
                        | "SHORT_ANSWER",
                    })
                  }
                >
                  {QUESTION_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">
                  Correct Answer <span className="text-[#ef4444]">*</span>
                </label>
                <textarea
                  className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full resize-none"
                  rows={2}
                  value={form.correct_answer}
                  onChange={(e) =>
                    setForm({ ...form, correct_answer: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">
                  Explanation
                </label>
                <textarea
                  className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full resize-none"
                  rows={3}
                  value={form.explanation}
                  onChange={(e) =>
                    setForm({ ...form, explanation: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">
                  Difficulty (1.0–5.0)
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  step="0.1"
                  className="border border-[#eaecf0] rounded-md text-[12px] text-[#374151] bg-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#1a5c38] w-full"
                  value={form.difficulty_level}
                  onChange={(e) =>
                    setForm({ ...form, difficulty_level: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-[10px] text-[#374151] font-medium mb-1 block">
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
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[#eaecf0] px-5 py-4 flex justify-end items-center gap-3">
          {error && (
            <span
              role="alert"
              className="text-[10px] text-[#ef4444] text-right mr-auto"
            >
              {error}
            </span>
          )}
          <button
            onClick={onClose}
            className="border border-[#eaecf0] bg-white text-[#374151] text-[11px] font-semibold px-4 py-2 rounded-md hover:bg-[#f3f4f6]"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !isFormValid}
            className="bg-[#1a5c38] text-white text-[11px] font-semibold px-4 py-2 rounded-md hover:bg-[#155231] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
