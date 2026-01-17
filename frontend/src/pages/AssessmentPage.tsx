// src/components/Assessment/AssessmentPage.tsx
import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { http } from "@/lib/http";
import config from "../config";
import { Breadcrumb } from "@/components/ui/Breadcrumb";

type QuestionBank = {
  id: number;
  question_text: string;
  question_type: string;
  options?: string[] | null;
  correct_answer?: string;
  difficulty_level?: string;
  learning_objectives: string
};

type Question = {
  id: number;
  question_number: number;
  question_bank: QuestionBank;
};

type AnswerResponse = {
  question_id: number;
  is_correct: boolean;
  score: number;
  feedback?: string;
  next_question?: Question | null;
};

const AssessmentPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [assessment, setAssessment] = useState<any>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subject, setSubject] = useState<string | null>(null);

  // ✅ Extract subject from query string
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const subjectParam = params.get("subject");
    setSubject(subjectParam); // fallback if none passed
  }, [location.search]);

  // ✅ Start or resume assessment
  useEffect(() => {
    if (subject) startOrResume();
    // eslint-disable-next-line
  }, [subject]);

  const startOrResume = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token")
      const localUser = localStorage.getItem("user")

      // No token or localUser → force login
      if (!token || !localUser) {
        console.error("Missing token or user. Redirecting.")
        window.location.href = "/student-login"
        return
      }
      // Parse user and check role
      let parsedUser: any
      try {
        parsedUser = JSON.parse(localUser)

        if (!parsedUser?.role || parsedUser.role.toLowerCase() !== "student") {
          console.error("User is not a student")
          window.location.href = "/student-login"
          return
        }
      } catch (err) {
        console.error("Invalid user JSON")
        window.location.href = "/student-login"
        return
      }

      //  create or get assessment
      const resp = await http.post(
        "/api/v1/assessments/",
        {
          student_id: parsedUser.student_profile.id,
          subject: subject,
        }
      );

      const body = resp.data;
      setAssessment(body);
      console.log(`Assessment for ${subject}:`, body);

      const nextUnanswered =
        body.questions?.find((q: any) => !q.student_answer) || null;

      if (nextUnanswered) {
        setQuestion(stripServerFields(nextUnanswered));
      } else {
        const qResp = await http.post(`/api/v1/assessments/${body.id}/questions`);
        const nq = qResp.data.questions?.find((q: any) => !q.student_answer) || null;
        setQuestion(nq ? stripServerFields(nq) : null);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const stripServerFields = (q: any) => {
    if (!q) return null;
    const { correct_answer, ai_feedback, ...client } = q;
    return client as Question;
  };

  // ✅ Submit answer
  const submitAnswer = async (timeTaken = 15, hintsUsed = 0) => {
    if (!question || !assessment) return;
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const resp = await http.post<AnswerResponse>(
        `/api/v1/assessments/${assessment.id}/questions/${question.id}/answer`,
        {
          answer_text: answer,
          time_taken: timeTaken,
          hints_used: hintsUsed,
        }
      );

      const body = resp.data;
      alert(body.feedback || (body.is_correct ? "✅ Correct!" : "❌ Not correct"));

      if (body.next_question) {
        setQuestion(stripServerFields(body.next_question));
        setAnswer("");
      } else if (body.status === "completed") {
        // Finished — show report
        const r = await http.get(`/api/v1/assessments/${assessment.id}/completed`);
        setReport(r.data);
        setTimeout(() => navigate("/child-dashboard"), 2500);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ✅ Render states
  if (loading && !question) {
    return <div className="p-6">Loading {subject} Assessment...</div>;
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-600">
        <p>Error: {error}</p>
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
        <h2 className="text-2xl font-bold">{subject} Assessment Report</h2>
        <pre className="bg-white p-4 rounded mt-4">
          {JSON.stringify(report.recommendations || report, null, 2)}
        </pre>
        <p className="mt-4 text-gray-600">Redirecting to dashboard...</p>
      </div>
    );
  }

  if (!question) {
    return <div className="p-6">No question loaded</div>;
  }

  // Main question UI
  return (
    <div className="min-h-screen p-6 bg-gray-50">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">
        <Breadcrumb role="student" items={[{ label: `${subject} Assessment` }]} />
        <div className="text-sm text-gray-500">
          {subject} • Question {question.question_number} • {question.question_bank.difficulty_label}
        </div>
        <h3 className="text-xl font-semibold mt-2">
          {question.question_number}.{" "}
          {question.question_bank.question_text}
          </h3>

        {question.question_bank.options && question.question_bank.options.length ? (
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
                  name="choice"
                  value={opt}
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

        <div className="mt-4 flex justify-end space-x-3">
          <button
            onClick={() => navigate("/child-dashboard")}
            className="px-4 py-2 rounded border"
          >
            Exit
          </button>
          <button
            onClick={() => submitAnswer()}
            disabled={loading || !answer}
            className="px-4 py-2 rounded bg-blue-600 text-white"
          >
            {loading ? "..." : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AssessmentPage;
