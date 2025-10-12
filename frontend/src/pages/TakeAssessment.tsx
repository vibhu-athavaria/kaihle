// src/components/Assessment/TakeAssessment.tsx
import React, { useState } from "react";
import axios from "axios";
import config from "../config";

axios.defaults.baseURL = config.backendUrl;

const TakeAssessment: React.FC = () => {
  const [subject, setSubject] = useState("Math");
  const [gradeLevel, setGradeLevel] = useState("Grade 7");
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [assessmentId, setAssessmentId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleStartAssessment = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        console.error("No token found, redirecting to login");
        window.location.href = "/parent-login";
        return;
      }

      const response = await axios.post("/api/v1/assessments/", {
        student_id: JSON.parse(localStorage.getItem("currentChild") || "{}").id,
        subject: subject,
        grade_level: gradeLevel,
        topic: topic || null,
      });

      const assessment = response.data;
      console.log("Assessment started:", assessment);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-blue-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              Take an Assessment
            </h2>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          <div className="mb-2">
            <label className="block text-sm font-medium">Subject</label>
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full p-2 border rounded"
            >
              <option value="Math">Math</option>
              <option value="Science">Science</option>
              <option value="English">English</option>
            </select>
          </div>

          <div className="mb-2">
            <label className="block text-sm font-medium">Grade Level</label>
            <select
              value={gradeLevel}
              onChange={(e) => setGradeLevel(e.target.value)}
              className="w-full p-2 border rounded"
            >
              <option value="Grade 6">Grade 6</option>
              <option value="Grade 7">Grade 7</option>
              <option value="Grade 8">Grade 8</option>
            </select>
          </div>

          <div className="mb-2">
            <label className="block text-sm font-medium">
              Topic (optional)
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full p-2 border rounded"
              placeholder="e.g. Algebra"
            />
          </div>

          <button
            onClick={handleStartAssessment}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            {loading ? "Starting..." : "Take Assessment"}
          </button>

          {assessmentId && (
            <p className="text-green-600 mt-2">
              Assessment started! ID: {assessmentId}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default TakeAssessment;
