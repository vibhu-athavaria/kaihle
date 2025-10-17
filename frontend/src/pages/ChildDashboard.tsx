"use client"

import React, { useEffect, useState } from "react"
import { BookOpen, Beaker, Edit3, Globe2 } from "lucide-react"
import { Child } from "../types"
import { SUBJECTS } from "../lib/utils"

const subjectIcons = {
  Math: BookOpen,
  Science: Beaker,
  English: Edit3,
  Humanities: Globe2,
}

type Subject = "Math" | "Science" | "English" | "Humanities"

interface StudyPlanItem {
  id: string
  title: string
  description: string
  difficulty: string
}

export const ChildDashboard: React.FC = () => {
  const [child, setChild] = useState<Child | null>(null)
  const [activeSubject, setActiveSubject] = useState<Subject>(SUBJECTS[0] as Subject)
  const [completedAssessments, setCompletedAssessments] = useState<Record<Subject, boolean>>({
    Math: false,
    Science: false,
    English: false,
    Humanities: false,
  })

  const [studyPlans, setStudyPlans] = useState<Record<Subject, StudyPlanItem[]>>({
    Math: [],
    Science: [],
    English: [],
    Humanities: [],
  })

  useEffect(() => {
    const storedChild = localStorage.getItem("currentChild")
    if (storedChild) {
      const parsed = JSON.parse(storedChild)
      setChild(parsed)

      // mock: assume the backend will return which subjects have assessments done
      setCompletedAssessments({
        Math: parsed.user.assessments?.Math || false,
        Science: parsed.user.assessments?.Science || false,
        English: parsed.user.assessments?.English || false,
        Humanities: parsed.user.assessments?.Humanities || false,
      })
    }

    // mock data for study plans
    setStudyPlans({
      Math: [
        { id: "m1", title: "Mastering Fractions", description: "Deep dive into operations with fractions.", difficulty: "Intermediate" },
        { id: "m2", title: "Geometry Basics", description: "Shapes, angles, and area calculation.", difficulty: "Beginner" },
      ],
      Science: [
        { id: "s1", title: "Forces & Motion", description: "Understand Newton’s laws and motion.", difficulty: "Intermediate" },
        { id: "s2", title: "Cells and Microorganisms", description: "Explore the building blocks of life.", difficulty: "Beginner" },
      ],
      English: [
        { id: "e1", title: "Creative Writing", description: "Build your storytelling and writing style.", difficulty: "Intermediate" },
        { id: "e2", title: "Reading Comprehension", description: "Learn to analyze complex passages.", difficulty: "Beginner" },
      ],
      Humanities: [
        { id: "h1", title: "Ancient Civilizations", description: "Discover the roots of human culture.", difficulty: "Intermediate" },
        { id: "h2", title: "World Geography", description: "Explore continents, cultures, and history.", difficulty: "Beginner" },
      ],
    })
  }, [])

  const handleStartAssessment = (subject: Subject) => {
    window.location.href = `/take-assessment?subject=${subject}`
  }

  if (!child) return null

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Welcome back, {child.user?.full_name}!
          </h1>
          <p className="text-gray-600">
            Choose a subject to continue your learning journey.
          </p>
        </div>

        {/* Subject Tabs */}
        <div className="mb-8">
          <div className="border-b border-gray-200 flex space-x-6 overflow-x-auto">
            {(SUBJECTS).map((subject) => (
              <button
                key={subject}
                onClick={() => setActiveSubject(subject as Subject)}
                className={`py-2 px-1 font-medium text-sm border-b-2 transition-all ${
                  activeSubject === subject
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {subject}
              </button>
            ))}
          </div>
        </div>

        {/* Active Tab Content */}
        <div>
          {!completedAssessments[activeSubject] ? (
            <div className="text-center py-16 bg-white rounded-xl shadow-sm">
              <div className="flex flex-col items-center space-y-4">
                {React.createElement(subjectIcons[activeSubject], { className: "w-12 h-12 text-blue-600" })}
                <h2 className="text-2xl font-semibold text-gray-900">
                  {activeSubject} Assessment
                </h2>
                <p className="text-gray-600 max-w-md">
                  Take the assessment to find your current level and unlock a personalized study plan for {activeSubject}.
                </p>
                <button
                  onClick={() => handleStartAssessment(activeSubject)}
                  className="bg-blue-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-blue-700 transition-all duration-200"
                >
                  Start {activeSubject} Assessment
                </button>
              </div>
            </div>
          ) : (
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                {activeSubject} Study Plan
              </h2>
              <div className="space-y-4">
                {studyPlans[activeSubject].map((item) => (
                  <div
                    key={item.id}
                    className="bg-white p-6 rounded-xl shadow-sm hover:shadow-md transition-all duration-200 flex items-start justify-between group"
                  >
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-1">{item.title}</h3>
                      <p className="text-gray-600 text-sm">{item.description}</p>
                      <p className="mt-2 text-sm font-medium text-blue-600">
                        Difficulty: {item.difficulty}
                      </p>
                    </div>
                    <button className="bg-blue-600 text-white hover:bg-blue-700 px-5 py-2 rounded-lg font-medium transition-colors">
                      Start Course
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ChildDashboard
