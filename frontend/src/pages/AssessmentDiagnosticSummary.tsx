import React, { useEffect, useState } from "react";
import { http } from "@/lib/http";
import {
  BookOpen,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Target,
  Award,
  BarChart3,
} from "lucide-react";
import { useLocation } from "react-router-dom";
import { Breadcrumb } from "@/components/ui/Breadcrumb";

interface AssessmentReport {
  score: number;
  total: number;
  topics: {
    name: string;
    correct: number;
    total: number;
  }[];
}

// interface AssessmentDiagnosticSummaryProps {
//   subject: string;
//   assessmentId: string;
//   cachedReport?: any;
//   onCacheReport: (id: string, data: any) => void;
//   onStartCourse: () => void;
// }

const AssessmentDiagnosticSummary: React.FC = () => {
  const [cachedReport, setCachedReport] = useState<any>(null);

  const onCacheReport = (id: string, data: any) => {
    setCachedReport(data);
  };

  const onStartCourse = () => {
    // Redirect to the personalized course page
    window.location.href = "/child-dashboard/take-micro-course"; // Adjust URL as needed
  };
  const location = useLocation();
  // Extract subject and assessmentId from query string
  const params = new URLSearchParams(location.search);
  const assessmentId = params.get("assessmentId") || "";
  const [subject, setSubject] = useState<string>("");
  const [assessmentCompleted, setAssessmentCompleted] = useState(false);
  const [assessmentReport, setAssessmentReport] =
    useState<AssessmentReport | null>(null);
  const [diagnosticSummary, setDiagnosticSummary] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  // -----------------------------------------
  // FETCH DATA ON MOUNT
  // -----------------------------------------
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const localUser = localStorage.getItem("user");

    if (!token || !localUser) {
      console.warn("Missing token/user");
      window.location.href = "/student-login";
      return;
    }

    let parsedUser: any = null;
    try {
      parsedUser = JSON.parse(localUser);
      if (!parsedUser?.role || parsedUser.role.toLowerCase() !== "student") {
        console.error("User is not a student");
        window.location.href = "/student-login";
        return;
      }
    } catch (err) {
      console.error("Invalid user JSON");
      window.location.href = "/student-login";
      return;
    }

    if (cachedReport) {
      console.log("Using cached report data");
      setSubject(cachedReport.subject);
      setAssessmentCompleted(cachedReport.completed);
      setAssessmentReport(cachedReport.assessment_report);
      setDiagnosticSummary(cachedReport.diagnostic_summary);
      setLoading(false);
      return;
    }
    const fetchAssessment = async () => {
      try {
        const res = await http.get(`/api/v1/assessments/${assessmentId}/report`);

        const data = await res.data;
        console.log("Assessment Report Data:", data);
        // Store in parent cache
        onCacheReport(assessmentId, data);
        setSubject(data.subject);
        setAssessmentCompleted(data.completed);
        setAssessmentReport(data.assessment_report);
        setDiagnosticSummary(data.diagnostic_summary);
      } catch (err) {
        console.error("Error fetching assessment data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchAssessment();
  }, [assessmentId, cachedReport]);

  // -----------------------------------------
  // UTIL FUNCTIONS (unchanged)
  // -----------------------------------------

  const parseDiagnosticSummary = (text: string) => {
    const lines = text
      .trim()
      .split("\n")
      .filter((line) => line.trim());
    const result = {
      title: undefined as string | undefined,
      strongAreas: [] as string[],
      developingAreas: [] as string[],
      supportAreas: [] as string[],
      explanation: undefined as string | undefined,
    };

    let currentSection = "";

    lines.forEach((line) => {
      const trimmed = line.trim();

      if (trimmed.includes("Diagnostic Summary for")) {
        result.title = trimmed;
      } else if (trimmed.includes("Strong Areas:")) {
        currentSection = "strong";
        const content = trimmed.split("Strong Areas:")[1]?.trim();
        if (content) result.strongAreas.push(content);
      } else if (trimmed.includes("Developing Areas:")) {
        currentSection = "developing";
        const content = trimmed.split("Developing Areas:")[1]?.trim();
        if (content) result.developingAreas.push(content);
      } else if (trimmed.includes("Areas Needing Support:")) {
        currentSection = "support";
        const content = trimmed.split("Areas Needing Support:")[1]?.trim();
        if (content) result.supportAreas.push(content);
      } else if (trimmed.startsWith("-")) {
        const item = trimmed.substring(1).trim();
        if (currentSection === "strong") result.strongAreas.push(item);
        else if (currentSection === "developing")
          result.developingAreas.push(item);
        else if (currentSection === "support") result.supportAreas.push(item);
      } else if (trimmed.includes("We will now create")) {
        result.explanation = trimmed;
      }
    });

    return result;
  };

  const calculatePercentage = (correct: number, total: number) =>
    Math.round((correct / total) * 100);

  const getPerformanceLevel = (percentage: number): string => {
    if (percentage >= 90) return "Advanced";
    if (percentage >= 75) return "Proficient";
    if (percentage >= 60) return "Developing";
    return "Needs Support";
  };
  // -----------------------------------------
  // UI LOGIC
  // -----------------------------------------

  if (loading) return <p>Loading assessment...</p>;
  if (!assessmentCompleted) return null;

  const parsed = diagnosticSummary
    ? parseDiagnosticSummary(diagnosticSummary)
    : null;
  const overallPercentage = assessmentReport
    ? calculatePercentage(assessmentReport.score, assessmentReport.total)
    : 0;

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Breadcrumb role="student" items={[{ label: "Assessment Report" }]} />
        <div className="space-y-6">
          {/* Overall Performance Hero Card */}
          {assessmentReport && (
            <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl shadow-lg p-8 text-white">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Award className="w-6 h-6" />
                    <h2 className="text-2xl font-bold">Assessment Complete!</h2>
                  </div>
                  <p className="text-blue-100">
                    Great job completing your {subject} assessment
                  </p>
                </div>
                <div className="bg-white/20 backdrop-blur-sm rounded-lg px-4 py-2">
                  <p className="text-sm opacity-90">Overall Score</p>
                  <p className="text-3xl font-bold">{overallPercentage}%</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 bg-white/10 backdrop-blur-sm rounded-lg p-4">
                <div className="text-center">
                  <p className="text-4xl font-bold">{assessmentReport.score}</p>
                  <p className="text-sm text-blue-100 mt-1">Correct Answers</p>
                </div>
                <div className="text-center border-l border-r border-white/20">
                  <p className="text-4xl font-bold">{assessmentReport.total}</p>
                  <p className="text-sm text-blue-100 mt-1">Total Questions</p>
                </div>
                <div className="text-center">
                  <p className="text-4xl font-bold">
                    {assessmentReport.topics.length}
                  </p>
                  <p className="text-sm text-blue-100 mt-1">Topics Covered</p>
                </div>
              </div>
            </div>
          )}

          {/* Diagnostic Summary - Performance Breakdown */}
          {parsed && (
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-2 mb-6">
                <BarChart3 className="w-6 h-6 text-blue-600" />
                <h3 className="text-xl font-bold text-gray-900">
                  Performance Analysis
                </h3>
              </div>

              <div className="grid md:grid-cols-3 gap-4 mb-6">
                {/* Strong Areas */}
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                      <CheckCircle2 className="w-5 h-5 text-green-600" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-900">
                        Strong Areas
                      </h4>
                      <p className="text-xs text-gray-600">Well understood</p>
                    </div>
                  </div>
                  <ul className="space-y-2">
                    {parsed.strongAreas.length > 0 ? (
                      parsed.strongAreas.map((area, idx) => (
                        <li
                          key={idx}
                          className="text-sm text-gray-700 flex items-start gap-2"
                        >
                          <span className="text-green-600 mt-0.5">✓</span>
                          <span>{area}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-sm text-gray-500 italic">
                        Building mastery...
                      </li>
                    )}
                  </ul>
                </div>

                {/* Developing Areas */}
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
                      <TrendingUp className="w-5 h-5 text-yellow-600" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-900">
                        Developing
                      </h4>
                      <p className="text-xs text-gray-600">Making progress</p>
                    </div>
                  </div>
                  <ul className="space-y-2">
                    {parsed.developingAreas.length > 0 ? (
                      parsed.developingAreas.map((area, idx) => (
                        <li
                          key={idx}
                          className="text-sm text-gray-700 flex items-start gap-2"
                        >
                          <span className="text-yellow-600 mt-0.5">↗</span>
                          <span>{area}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-sm text-gray-500 italic">
                        Keep learning!
                      </li>
                    )}
                  </ul>
                </div>

                {/* Needs Support */}
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                      <Target className="w-5 h-5 text-red-600" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-900">
                        Focus Areas
                      </h4>
                      <p className="text-xs text-gray-600">Priority topics</p>
                    </div>
                  </div>
                  <ul className="space-y-2">
                    {parsed.supportAreas.length > 0 ? (
                      parsed.supportAreas.map((area, idx) => (
                        <li
                          key={idx}
                          className="text-sm text-gray-700 flex items-start gap-2"
                        >
                          <span className="text-red-600 mt-0.5">!</span>
                          <span>{area}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-sm text-gray-500 italic">
                        Great progress!
                      </li>
                    )}
                  </ul>
                </div>
              </div>

              {/* What This Means Section */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-gray-900 mb-2">
                      What This Means
                    </h4>
                    <div className="space-y-2 text-sm text-gray-700">
                      <p>
                        <strong>Strong Areas:</strong> Topics where you&apos;ve
                        demonstrated clear understanding.
                      </p>
                      <p>
                        <strong>Developing Areas:</strong> Topics that need more
                        practice and reinforcement.
                      </p>
                      <p>
                        <strong>Focus Areas:</strong> Foundational concepts
                        we&apos;ll prioritize in your learning plan.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Topic Performance Details */}
          {assessmentReport && (
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">
                Performance by Topic
              </h3>
              <div className="space-y-4">
                {assessmentReport.topics.map((topic, index) => {
                  const percentage = calculatePercentage(
                    topic.correct,
                    topic.total
                  );
                  const level = getPerformanceLevel(percentage);

                  return (
                    <div
                      key={index}
                      className={`border ${level.borderColor} rounded-lg p-4 ${level.bgColor} transition-all hover:shadow-md`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3 flex-1">
                          <div
                            className={`w-12 h-12 ${level.bgColor} border-2 ${level.borderColor} rounded-lg flex items-center justify-center`}
                          >
                            <span
                              className="text-lg font-bold"
                              style={{
                                color:
                                  level.color === "green"
                                    ? "#15803d"
                                    : level.color === "yellow"
                                    ? "#a16207"
                                    : "#b91c1c",
                              }}
                            >
                              {percentage}%
                            </span>
                          </div>
                          <div className="flex-1">
                            <h4 className="font-semibold text-gray-900">
                              {topic.name}
                            </h4>
                            <p className="text-sm text-gray-600">
                              {topic.correct} of {topic.total} questions correct
                            </p>
                          </div>
                        </div>
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold ${level.textColor} bg-white border ${level.borderColor}`}
                        >
                          {level.label}
                        </span>
                      </div>

                      {/* Visual Progress Bar */}
                      <div className="relative w-full h-3 bg-white rounded-full overflow-hidden border border-gray-200">
                        <div
                          className="h-full transition-all duration-500 rounded-full"
                          style={{
                            width: `${percentage}%`,
                            background:
                              level.color === "green"
                                ? "linear-gradient(90deg, #22c55e 0%, #16a34a 100%)"
                                : level.color === "yellow"
                                ? "linear-gradient(90deg, #eab308 0%, #ca8a04 100%)"
                                : "linear-gradient(90deg, #ef4444 0%, #dc2626 100%)",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Next Steps & Start Course */}
          <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl shadow-lg p-6 text-white">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-lg flex items-center justify-center flex-shrink-0">
                  <BookOpen className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-xl font-bold mb-1">
                    Ready for Your Personalized Course?
                  </h3>
                  <p className="text-blue-100 text-sm">
                    We&apos;ve created a custom learning path based on your
                    assessment results to help you master {subject}.
                  </p>
                </div>
              </div>
              <button
                onClick={onStartCourse}
                className="bg-white text-blue-600 px-8 py-3 rounded-xl font-semibold hover:bg-blue-50 transition-all duration-200 shadow-lg whitespace-nowrap"
              >
                Start {subject} Course
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AssessmentDiagnosticSummary;
