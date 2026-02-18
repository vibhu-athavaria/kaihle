// src/components/Assessment/AssessmentPage.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { http } from "@/lib/http";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { useAuth } from "@/contexts/AuthContext";

/* ----------------------------- */
/* Types */
/* ----------------------------- */

type Assessment = {
  id: number;
  status: "in_progress" | "completed";
  subject_id: string;
};

type QuestionBank = {
  id: number;
  question_text: string;
  question_type: string;
  options?: string[] | null;
  difficulty_label?: string;
  meta_tags?: Record<string, any> | null;
};

type Question = {
  id: number;
  question_number: number;
  question_bank: QuestionBank;
};

type ResolveQuestionResponse =
  | { status: "question"; question: Question }
  | { status: "completed" };

type AnswerResponse = {
  is_correct: boolean;
  feedback?: string;
  next_question?: Question | null;
  status?: "completed";
};

/* ----------------------------- */
/* Component */
/* ----------------------------- */

const AssessmentPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);

  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<any | null>(null);

  /* ----------------------------- */
  /* Resolve assessment */
  /* ----------------------------- */

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const subject = params.get("subject_id");

    if (!subject) {
      setError("Missing subject_id");
      return;
    }

    setSubjectId(subject);
    if (!subjectId) {
      console.error("Missing subject_id");
      return;
    }
    if (!user?.student_profile?.id) {
      console.error("Missing student_id");
      return;
    }

    void resolveAssessmentAndQuestion();
}, [location.search, subjectId, user?.student_profile?.id]);

const resolveAssessmentAndQuestion = async () => {
  setLoading(true);
  setError(null);

  try {
    // resolve assessment
    const resp = await http.post<Assessment>(
      "/api/v1/assessments/resolve",
      {
        student_id: user.student_profile.id,
        subject_id: subjectId,
      }
    );

    const assessment = resp.data;
    setAssessment(assessment);

    // defensive guard (never assume backend correctness)
    if (!assessment?.id) {
      throw new Error("Assessment resolved without id");
    }

    // resolve question ONLY after assessment exists
    await resolveQuestion(assessment.id);

  } catch (err) {
    console.error(err);
    setError("Failed to start assessment");
  } finally {
    setLoading(false);
  }
};


  /* ----------------------------- */
  /* Resolve next question */
  /* ----------------------------- */

  const resolveQuestion = async (assessmentId: number) => {
    try {
      const resp = await http.post<ResolveQuestionResponse>(
        `/api/v1/assessments/${assessmentId}/questions/resolve`
      );

      // if (resp.data.status === "completed") {
      //   const r = await http.get(
      //     `/api/v1/assessments/${assessmentId}/completed`
      //   );
      //   setReport(r.data);
      //   setTimeout(() => navigate("/child-dashboard"), 2500);
      //   return;
      // }

      setQuestion(resp.data.question);
    } catch (err) {
      console.error(err);
      setError("Failed to load question");
    }
  };

  /* ----------------------------- */
  /* Submit answer */
  /* ----------------------------- */

  const submitAnswer = async () => {
    if (!assessment || !question) return;

    setLoading(true);

    try {
      const resp = await http.post<AnswerResponse>(
        `/api/v1/assessments/${assessment.id}/questions/${question.id}/answer`,
        { answer_text: answer }
      );

      alert(
        resp.data.feedback ||
          (resp.data.is_correct ? "✅ Correct!" : "❌ Not correct")
      );

      if (resp.data.next_question) {
        setQuestion(resp.data.next_question);
        setAnswer("");
        return;
      }

      if (resp.data.status === "completed") {
        const r = await http.get(
          `/api/v1/assessments/${assessment.id}/completed`
        );
        setReport(r.data);
        setTimeout(() => navigate("/child-dashboard"), 2500);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to submit answer");
    } finally {
      setLoading(false);
    }
  };

  /* ----------------------------- */
  /* Render states */
  /* ----------------------------- */

  if (loading && !question) {
    return <div className="p-6">Loading assessment...</div>;
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-600">
        <p>{error}</p>
        <button
          onClick={() => navigate("/child-dashboard")}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded"
        >
          Go Back
        </button>
      </div>
    );
  }

  if (report) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <h2 className="text-2xl font-bold">Assessment Report</h2>
        <pre className="bg-white p-4 rounded mt-4">
          {JSON.stringify(report, null, 2)}
        </pre>
        <p className="mt-4 text-gray-600">Redirecting to dashboard...</p>
      </div>
    );
  }

  if (!question) {
    return <div className="p-6">No question loaded</div>;
  }

  /* ----------------------------- */
  /* Main UI */
  /* ----------------------------- */

  return (
    <div className="min-h-screen p-6 bg-gray-50">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">
        <Breadcrumb
          role="student"
          items={[{ label: "Assessment" }]}
        />

        <div className="text-sm text-gray-500">
          Question {question.question_number} •{" "}
          {question.question_bank.difficulty_label}
        </div>

        <h3 className="text-xl font-semibold mt-2">
          {question.question_number}.{" "}
          {question.question_bank.question_text}
        </h3>

        {question.question_bank.meta_tags && (
          <div className="mt-2 flex flex-wrap gap-1">
            {Object.entries(question.question_bank.meta_tags).map(([key, value]) => (
              <span
                key={key}
                className="inline-block px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full"
              >
                {key}: {String(value)}
              </span>
            ))}
          </div>
        )}

        {question.question_bank.options?.length ? (
          <div className="mt-4 space-y-2">
            {question.question_bank.options.map((opt, i) => (
              <label
                key={i}
                className={`block p-3 rounded border cursor-pointer ${
                  answer === opt
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200"
                }`}
              >
                <input
                  type="radio"
                  checked={answer === opt}
                  onChange={() => setAnswer(opt)}
                  className="mr-2"
                />
                {opt}
              </label>
            ))}
          </div>
        ) : (
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={4}
            className="w-full p-3 border rounded mt-4"
          />
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={() => navigate("/child-dashboard")}
            className="px-4 py-2 rounded border"
          >
            Exit
          </button>

          <button
            onClick={submitAnswer}
            disabled={!answer || loading}
            className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {loading ? "..." : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AssessmentPage;
