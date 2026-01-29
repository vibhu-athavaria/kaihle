import React, { useState } from "react";
import {
  Video,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Target,
  Lightbulb,
  PlayCircle,
  Award,
  ArrowRight,
  Circle,
  Check,
  X,
  Sparkles,
} from "lucide-react";

import { Breadcrumb } from "@/components/ui/Breadcrumb";
interface QuizItem {
  question: string;
  options: string[];
  answer?: string;
}

interface CourseProps {
  title: string;
  subtopic: string;
  videoUrl?: string;
  textContent?: string;
  learningObjectives?: string[];
  outcomes?: string[];
  guidedProblems?: string[];
  quiz?: QuizItem[];
}

type Section =
  | "objectives"
  | "video"
  | "explanation"
  | "practice"
  | "quiz"
  | "apply";

// --------------------------
// Hardcoded course
// --------------------------
const HARDCODED_COURSE = {
  title: "Understanding Area and Perimeter",
  subtopic: "Geometry Basics",
  videoUrl: "https://www.youtube.com/embed/dQw4w9WgXcQ",
  textContent:
    "Area and perimeter are two fundamental concepts in geometry that help us measure shapes.\
    \
    **Perimeter** is the distance around the outside of a shape. To find the perimeter, you add up the lengths of all the sides.\
    \
    For example, if you have a rectangle with length 5 cm and width 3 cm:\
    Perimeter = 5 + 3 + 5 + 3 = 16 cm\
    \
    **Area** is the amount of space inside a shape. For rectangles, you multiply the length by the width.\
    \
    Using the same rectangle:\
    Area = 5 × 3 = 15 cm²\
    \
    Remember: Perimeter is measured in units (cm, m, etc.) while area is measured in square units (cm², m², etc.).",
  learningObjectives: [
    "Understand the difference between area and perimeter",
    "Calculate the perimeter of rectangles and squares",
    "Calculate the area of rectangles and squares",
    "Apply formulas to solve real-world problems",
  ],
  outcomes: [
    "Confidently measure the perimeter of any rectangular shape",
    "Calculate area using the correct formula",
    "Recognize when to use area vs perimeter in real situations",
  ],
  guidedProblems: [
    "A rectangular garden is 8 meters long and 5 meters wide. What is its perimeter?",
    "If the same garden needs to be covered with grass, what is the area that needs grass?",
    "A square room has sides of 4 meters. Find both the perimeter and area.",
    "A rectangular field is 12 feet long and 7 feet wide. Calculate the perimeter.",
    "What is the area of a rectangle with length 9 cm and width 6 cm?",
  ],
  quiz: [
    {
      question:
        "What is the perimeter of a rectangle with length 6 cm and width 4 cm?",
      options: ["10 cm", "20 cm", "24 cm", "40 cm"],
      answer: "20 cm",
    },
    {
      question: "What is the area of a square with sides of 5 meters?",
      options: ["20 m²", "25 m²", "10 m²", "50 m²"],
      answer: "25 m²",
    },
    {
      question:
        "If you want to put a fence around a garden, are you measuring area or perimeter?",
      options: ["Area", "Perimeter", "Both", "Neither"],
      answer: "Perimeter",
    },
    {
      question:
        "What is the area of a rectangle with length 8 cm and width 3 cm?",
      options: ["11 cm²", "22 cm²", "24 cm²", "64 cm²"],
      answer: "24 cm²",
    },
  ],
};

export default function CoursePage({
  title = "Untitled Lesson",
  subtopic = "",
  videoUrl = "",
  textContent = "",
  learningObjectives = [],
  outcomes = [],
  guidedProblems = [],
  quiz = [],
}: CourseProps) {
  const [course, setCourse] = useState({});
  const [currentSection, setCurrentSection] = useState<Section>("objectives");
  const [completedSections, setCompletedSections] = useState<Section[]>([]);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({});
  const [showQuizResults, setShowQuizResults] = useState(false);
  const [videoWatched, setVideoWatched] = useState(false);

  const sections: { id: Section; label: string; icon: any; color: string }[] = [
    { id: "objectives", label: "Learning Goals", icon: Target, color: "blue" },
    { id: "video", label: "Watch Video", icon: Video, color: "purple" },
    {
      id: "explanation",
      label: "Learn Concept",
      icon: BookOpen,
      color: "indigo",
    },
    { id: "practice", label: "Practice", icon: ClipboardList, color: "orange" },
    { id: "quiz", label: "Quiz", icon: CheckCircle2, color: "red" },
    { id: "apply", label: "Apply It", icon: Lightbulb, color: "emerald" },
  ];

  const markSectionComplete = (section: Section) => {
    if (!completedSections.includes(section)) {
      setCompletedSections([...completedSections, section]);
    }
  };

  const handleQuizAnswer = (questionIndex: number, answer: string) => {
    setQuizAnswers({ ...quizAnswers, [questionIndex]: answer });
  };

  const submitQuiz = () => {
    setShowQuizResults(true);
    markSectionComplete("quiz");
  };

  const calculateQuizScore = () => {
    let correct = 0;
    quiz.forEach((q, i) => {
      if (quizAnswers[i] === q.answer) correct++;
    });
    return { correct, total: quiz.length };
  };

  const progressPercentage = (completedSections.length / sections.length) * 100;

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <Breadcrumb role="student" items={[{ label: "Course" }]} />
        {/* Hero Header with Progress */}
        <div className="bg-gradient-to-br from-blue-600 to-purple-600 text-white rounded-xl shadow-lg p-6 mb-8">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <BookOpen className="w-6 h-6" />
                <span className="text-sm opacity-90">Micro Course</span>
              </div>
              <h1 className="text-3xl font-bold mb-1">{title}</h1>
              <p className="text-blue-100">{subtopic}</p>
            </div>
            <div className="bg-white/20 backdrop-blur-sm rounded-lg px-4 py-2 text-center">
              <div className="text-3xl font-bold">
                {Math.round(progressPercentage)}%
              </div>
              <div className="text-xs opacity-90">Complete</div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-white/20 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-white transition-all duration-500 rounded-full"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>

          {/* Progress Steps */}
          <div className="grid grid-cols-6 gap-2 mt-4">
            {sections.map((section) => {
              const isComplete = completedSections.includes(section.id);
              const isCurrent = currentSection === section.id;
              return (
                <button
                  key={section.id}
                  onClick={() => setCurrentSection(section.id)}
                  className={`flex flex-col items-center gap-1 p-2 rounded-lg transition-all ${
                    isCurrent
                      ? "bg-white/30 backdrop-blur-sm"
                      : "hover:bg-white/10"
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      isComplete ? "bg-green-500" : "bg-white/20"
                    }`}
                  >
                    {isComplete ? (
                      <Check className="w-4 h-4 text-white" />
                    ) : (
                      <Circle className="w-3 h-3 text-white" />
                    )}
                  </div>
                  <span className="text-xs text-center opacity-90">
                    {section.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Learning Objectives Section */}
        {currentSection === "objectives" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <Target className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Learning Objectives
                  </h2>
                  <p className="text-gray-600">
                    What you&apos;ll master in this lesson
                  </p>
                </div>
              </div>

              <div className="space-y-3 mb-6">
                {learningObjectives.length > 0 ? (
                  learningObjectives.map((obj, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-lg p-4"
                    >
                      <div className="w-6 h-6 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-white text-sm">{i + 1}</span>
                      </div>
                      <p className="text-gray-700 flex-1">{obj}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500 text-center py-8">
                    No learning objectives provided.
                  </p>
                )}
              </div>

              {/* Expected Outcomes */}
              {outcomes.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-6 mt-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Lightbulb className="w-5 h-5 text-green-600" />
                    <h3 className="font-semibold text-gray-900">
                      By the end, you&apos;ll be able to:
                    </h3>
                  </div>
                  <ul className="space-y-2">
                    {outcomes.map((outcome, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-gray-700"
                      >
                        <CheckCircle2 className="w-4 h-4 text-green-600 mt-1 flex-shrink-0" />
                        <span>{outcome}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <button
              onClick={() => {
                markSectionComplete("objectives");
                setCurrentSection("video");
              }}
              className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-2"
            >
              Continue to Video <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Video Section */}
        {currentSection === "video" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                  <Video className="w-6 h-6 text-purple-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Lesson Video
                  </h2>
                  <p className="text-gray-600">
                    Watch this 3–7 minute explanation
                  </p>
                </div>
              </div>

              <div className="relative w-full rounded-xl overflow-hidden bg-gray-900 aspect-video">
                {videoUrl ? (
                  <iframe
                    src={videoUrl}
                    className="w-full h-full"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    title={`lesson-video-${subtopic}`}
                    onLoad={() => setVideoWatched(true)}
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-purple-600 to-blue-600 text-white">
                    <PlayCircle className="w-16 h-16 mb-4 opacity-50" />
                    <p className="text-lg">
                      No video available for this lesson
                    </p>
                    <p className="text-sm opacity-75 mt-2">
                      Skip to the explanation below
                    </p>
                  </div>
                )}
              </div>

              {videoUrl && !videoWatched && (
                <div className="mt-4 bg-purple-50 border border-purple-200 rounded-lg p-4 flex items-start gap-3">
                  <PlayCircle className="w-5 h-5 text-purple-600 mt-0.5" />
                  <p className="text-sm text-gray-700">
                    <strong>Tip:</strong> Watch the entire video to understand
                    the concept better. Take notes if needed!
                  </p>
                </div>
              )}
            </div>

            <div className="flex gap-4">
              <button
                onClick={() => setCurrentSection("objectives")}
                className="flex-1 bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-all"
              >
                Back
              </button>
              <button
                onClick={() => {
                  markSectionComplete("video");
                  setCurrentSection("explanation");
                }}
                className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-2"
              >
                Continue to Explanation <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Explanation Section */}
        {currentSection === "explanation" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
                  <BookOpen className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Detailed Explanation
                  </h2>
                  <p className="text-gray-600">
                    Read and understand the concept
                  </p>
                </div>
              </div>

              {textContent ? (
                <div className="prose max-w-none">
                  <div className="bg-indigo-50 border-l-4 border-indigo-600 rounded-r-lg p-6">
                    <p className="text-gray-800 leading-relaxed whitespace-pre-line">
                      {textContent}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  No explanation text provided.
                </p>
              )}
            </div>

            <div className="flex gap-4">
              <button
                onClick={() => setCurrentSection("video")}
                className="flex-1 bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-all"
              >
                Back
              </button>
              <button
                onClick={() => {
                  markSectionComplete("explanation");
                  setCurrentSection("practice");
                }}
                className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-2"
              >
                Continue to Practice <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Practice Section */}
        {currentSection === "practice" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center">
                  <ClipboardList className="w-6 h-6 text-orange-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Guided Practice
                  </h2>
                  <p className="text-gray-600">
                    Work through these {guidedProblems.length} problems
                  </p>
                </div>
              </div>

              {guidedProblems.length > 0 ? (
                <div className="space-y-4">
                  {guidedProblems.map((problem, i) => (
                    <div
                      key={i}
                      className="bg-orange-50 border border-orange-200 rounded-lg p-5"
                    >
                      <div className="flex items-start gap-4">
                        <div className="w-8 h-8 bg-orange-600 rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-white font-bold">{i + 1}</span>
                        </div>
                        <div className="flex-1">
                          <p className="text-gray-800 mb-3">{problem}</p>
                          <textarea
                            placeholder="Write your answer here..."
                            className="w-full border border-orange-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-orange-500 bg-white"
                            rows={2}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  No practice problems available.
                </p>
              )}

              <div className="mt-6 bg-orange-50 border border-orange-200 rounded-lg p-4 flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-orange-600 mt-0.5" />
                <p className="text-sm text-gray-700">
                  <strong>Pro Tip:</strong> Work through each problem step by
                  step. It&apos;s okay to make mistakes – that&apos;s how we
                  learn!
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <button
                onClick={() => setCurrentSection("explanation")}
                className="flex-1 bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-all"
              >
                Back
              </button>
              <button
                onClick={() => {
                  markSectionComplete("practice");
                  setCurrentSection("quiz");
                }}
                className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-2"
              >
                Ready for Quiz <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Quiz Section */}
        {currentSection === "quiz" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6 text-red-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Quick Quiz
                  </h2>
                  <p className="text-gray-600">
                    Test your understanding with {quiz.length} questions
                  </p>
                </div>
              </div>

              {quiz.length > 0 ? (
                <div className="space-y-6">
                  {quiz.map((q, index) => {
                    const userAnswer = quizAnswers[index];
                    const isCorrect =
                      showQuizResults && userAnswer === q.answer;
                    const isWrong =
                      showQuizResults && userAnswer && userAnswer !== q.answer;

                    return (
                      <div
                        key={index}
                        className={`border-2 rounded-lg p-5 transition-all ${
                          showQuizResults
                            ? isCorrect
                              ? "border-green-500 bg-green-50"
                              : isWrong
                              ? "border-red-500 bg-red-50"
                              : "border-gray-200"
                            : "border-gray-200"
                        }`}
                      >
                        <div className="flex items-start gap-3 mb-4">
                          <div
                            className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                              showQuizResults && isCorrect
                                ? "bg-green-600"
                                : showQuizResults && isWrong
                                ? "bg-red-600"
                                : "bg-gray-200"
                            }`}
                          >
                            {showQuizResults && isCorrect ? (
                              <Check className="w-5 h-5 text-white" />
                            ) : showQuizResults && isWrong ? (
                              <X className="w-5 h-5 text-white" />
                            ) : (
                              <span className="text-gray-700 font-bold">
                                {index + 1}
                              </span>
                            )}
                          </div>
                          <p className="font-semibold text-gray-900 flex-1">
                            {q.question}
                          </p>
                        </div>

                        <div className="space-y-2 pl-11">
                          {q.options.map((opt, i) => {
                            const isSelected = userAnswer === opt;
                            const isTheAnswer =
                              showQuizResults && q.answer === opt;

                            return (
                              <label
                                key={i}
                                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                                  showQuizResults && isTheAnswer
                                    ? "bg-green-100 border-2 border-green-500"
                                    : isSelected && !showQuizResults
                                    ? "bg-blue-100 border-2 border-blue-500"
                                    : "bg-gray-50 border-2 border-transparent hover:bg-gray-100"
                                }`}
                              >
                                <input
                                  type="radio"
                                  name={`quiz-${index}`}
                                  value={opt}
                                  checked={isSelected}
                                  onChange={(e) =>
                                    handleQuizAnswer(index, e.target.value)
                                  }
                                  disabled={showQuizResults}
                                  className="w-4 h-4"
                                />
                                <span className="text-gray-800">{opt}</span>
                                {showQuizResults && isTheAnswer && (
                                  <CheckCircle2 className="w-5 h-5 text-green-600 ml-auto" />
                                )}
                              </label>
                            );
                          })}
                        </div>

                        {showQuizResults && isWrong && (
                          <div className="mt-3 pl-11 text-sm text-red-700">
                            <strong>Correct answer:</strong> {q.answer}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {showQuizResults && (
                    <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6 text-white">
                      <div className="flex items-center gap-4">
                        <div className="w-16 h-16 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                          <Award className="w-8 h-8" />
                        </div>
                        <div className="flex-1">
                          <h3 className="text-xl font-bold mb-1">
                            Quiz Complete!
                          </h3>
                          <p className="text-blue-100">
                            You got {calculateQuizScore().correct} out of{" "}
                            {calculateQuizScore().total} correct (
                            {Math.round(
                              (calculateQuizScore().correct /
                                calculateQuizScore().total) *
                                100
                            )}
                            %)
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  No quiz available for this lesson.
                </p>
              )}
            </div>

            <div className="flex gap-4">
              <button
                onClick={() => setCurrentSection("practice")}
                className="flex-1 bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-all"
              >
                Back
              </button>
              {!showQuizResults ? (
                <button
                  onClick={submitQuiz}
                  disabled={Object.keys(quizAnswers).length < quiz.length}
                  className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  Submit Quiz <CheckCircle2 className="w-5 h-5" />
                </button>
              ) : (
                <button
                  onClick={() => setCurrentSection("apply")}
                  className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg flex items-center justify-center gap-2"
                >
                  Continue to Apply <ArrowRight className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Apply It Section */}
        {currentSection === "apply" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center">
                  <Lightbulb className="w-6 h-6 text-emerald-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Apply It: Real-World Task
                  </h2>
                  <p className="text-gray-600">
                    Use what you learned in a real situation
                  </p>
                </div>
              </div>

              <div className="bg-gradient-to-br from-emerald-50 to-green-50 border-2 border-emerald-300 rounded-xl p-6">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-emerald-600 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Sparkles className="w-6 h-6 text-white" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold text-gray-900 mb-3">
                      Your Challenge:
                    </h3>
                    <p className="text-gray-700 mb-4">
                      Apply the {subtopic} concept to a real-world scenario.
                      Think about how you can use this knowledge in your daily
                      life or schoolwork.
                    </p>
                    <textarea
                      placeholder="Describe how you'll apply this concept in the real world..."
                      className="w-full border-2 border-emerald-300 rounded-lg p-4 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                      rows={4}
                    />
                  </div>
                </div>
              </div>

              <div className="grid md:grid-cols-3 gap-4 mt-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                  <Target className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                  <h4 className="font-semibold text-gray-900 mb-1">
                    Set a Goal
                  </h4>
                  <p className="text-sm text-gray-600">
                    How will you practice this?
                  </p>
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
                  <ClipboardList className="w-8 h-8 text-purple-600 mx-auto mb-2" />
                  <h4 className="font-semibold text-gray-900 mb-1">
                    Take Action
                  </h4>
                  <p className="text-sm text-gray-600">Try it out today!</p>
                </div>
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                  <Award className="w-8 h-8 text-green-600 mx-auto mb-2" />
                  <h4 className="font-semibold text-gray-900 mb-1">
                    Celebrate
                  </h4>
                  <p className="text-sm text-gray-600">
                    You&apos;ve learned something new!
                  </p>
                </div>
              </div>
            </div>

            {/* Completion Celebration */}
            <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-xl shadow-lg p-8 text-white text-center">
              <div className="w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mx-auto mb-4">
                <Award className="w-10 h-10" />
              </div>
              <h2 className="text-3xl font-bold mb-2">Lesson Complete! 🎉</h2>
              <p className="text-green-100 mb-6">
                You&apos;ve finished the {title} micro course. Great job!
              </p>
              <button
                onClick={() => markSectionComplete("apply")}
                className="bg-white text-green-600 px-8 py-3 rounded-xl font-semibold hover:bg-green-50 transition-all shadow-lg"
              >
                Mark as Complete
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
