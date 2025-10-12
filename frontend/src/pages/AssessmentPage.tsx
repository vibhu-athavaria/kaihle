// src/components/Assessment/AssessmentPage.tsx
import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import config from "../config";

axios.defaults.baseURL = config.backendUrl;

type Question = {
  id: number;
  question_number: number;
  question_text: string;
  question_type: string;
  options?: string[] | null;
  difficulty_level?: string;
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
  const { assessmentId } = useParams<{ assessmentId: string }>();

  const [assessment, setAssessment] = useState<any>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ✅ Start or resume assessment
  useEffect(() => {
    startOrResume();
    // eslint-disable-next-line
  }, []);

  const startOrResume = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      const child = JSON.parse(localStorage.getItem("currentChild") || "{}");

      if (!token || !child?.id) {
        console.error("Missing token or child info");
        navigate("/parent-login");
        return;
      }

      const resp = await axios.post(
        "/api/v1/assessments/",
        {
          student_id: child.id,
          student_age: child.age,
          subject: "Adaptive",
          assessment_type: "diagnostic_adaptive",
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      const body = resp.data;
      setAssessment(body);
      console.log("Assessment response:", body);
      console.log("Questions:", body.questions);

      const nextUnanswered =
        body.questions?.find((q: any) => !q.student_answer) || null;

      if (nextUnanswered) {
        setQuestion(stripServerFields(nextUnanswered));
      } else {
        const qResp = await axios.get(`/api/v1/assessments/${body.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
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
      const resp = await axios.post<AnswerResponse>(
        `/api/v1/assessments/${assessment.id}/questions/${question.id}/answer`,
        {
          answer_text: answer,
          time_taken: timeTaken,
          hints_used: hintsUsed,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      const body = resp.data;
      alert(body.feedback || (body.is_correct ? "✅ Correct!" : "❌ Not correct"));

      if (body.next_question) {
        setQuestion(stripServerFields(body.next_question));
        setAnswer("");
      } else {
        // Finished — show report
        const r = await axios.get(`/api/v1/assessments/${assessment.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
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
    return <div className="p-6">Loading...</div>;
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
        <h2 className="text-2xl font-bold">Assessment Report</h2>
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

  // ✅ Main question UI
  return (
    <div className="min-h-screen p-6 bg-gray-50">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">
        <div className="text-sm text-gray-500">
          Question {question.question_number} • {question.difficulty_level}
        </div>
        <h3 className="text-xl font-semibold mt-2">{question.question_text}</h3>

        {question.options && question.options.length ? (
          <div className="mt-4 space-y-2">
            {question.options.map((opt, i) => (
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
