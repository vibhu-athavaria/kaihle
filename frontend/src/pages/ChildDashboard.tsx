"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Trophy, Sparkles, Lock, FileText, ArrowRight, PlayCircle, Award } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { http } from "@/lib/http";
import { useAuth } from "@/contexts/AuthContext";
import { Child } from "@/types";

import {
  Subject,
  AssessmentStatus,
  SUBJECT_UI,
  BADGES,
  BADGE_GRADIENTS,
} from "@/config/childDashboard";

/* ---------------------------------- */
/* Types */
/* ---------------------------------- */

interface SubjectData {
  name: Subject;
  status: AssessmentStatus;
  description: string;
  assessment_id?: number;
  progress?: number;
  level?: string;
}

/* ---------------------------------- */
/* Component */
/* ---------------------------------- */

export const ChildDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [child, setChild] = useState<Child | null>(null);
  const [subjects, setSubjects] = useState<Record<Subject, SubjectData>>({} as any);

  /* ---------------------------------- */
  /* Navigation */
  /* ---------------------------------- */

  const goToAssessment = (subject: Subject, resume = false) => {
    navigate(`/child-dashboard/assessment?subject=${subject}${resume ? "&resume=true" : ""}`);
  };

  const goToReport = (assessmentId: number) => {
    navigate(`/child-dashboard/assessment-diagnostic-report?assessmentId=${assessmentId}`);
  };

  const goToCourse = (subject: Subject) => {
    navigate(`/child-dashboard/take-micro-course?subject=${subject}`);
  };

  /* ---------------------------------- */
  /* Data mapping */
  /* ---------------------------------- */

  const mapSubjectFromApi = (subject: Subject, api: any): SubjectData => {
    const assessment = api?.assessments?.[subject];

    if (!assessment) {
      return {
        name: subject,
        status: "not_started",
        description: `Start your diagnostic test to discover your ${subject} level.`,
      };
    }

    if (assessment.status === "completed") {
      return {
        name: subject,
        status: "completed",
        level: assessment.level,
        assessment_id: assessment.assessment_id,
        description: "Great job! You've completed your diagnostic assessment.",
      };
    }

    return {
      name: subject,
      status: "in_progress",
      progress: assessment.progress ?? 0,
      assessment_id: assessment.assessment_id,
      description: `You're ${assessment.progress ?? 0}% through your diagnostic assessment.`,
    };
  };

  /* ---------------------------------- */
  /* Fetch student */
  /* ---------------------------------- */

  useEffect(() => {
    if (!user?.student_profile?.id) return;

    const fetchStudent = async () => {
      const res = await http.get(`/api/v1/students/${user.student_profile.id}`);
      setChild(res.data);

      const mapped = {} as Record<Subject, SubjectData>;
      (Object.keys(SUBJECT_UI) as Subject[]).forEach(
        (s) => (mapped[s] = mapSubjectFromApi(s, res.data))
      );
      setSubjects(mapped);
    };

    fetchStudent();
  }, [user]);

  if (!child) return null;

  /* ---------------------------------- */
  /* Render */
  /* ---------------------------------- */

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      <div className="max-w-7xl mx-auto p-6">

        {/* Header */}
        <div className="bg-white rounded-xl shadow p-6 mb-8 flex justify-between">
          <div>
            <h1 className="text-3xl font-bold">Welcome back, {child.user.full_name}!</h1>
            <p className="text-gray-600">Grade {child.grade_level}</p>
          </div>
          <div className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 py-2 rounded-full">
            <Trophy className="w-5 h-5" />
            3 Badges Earned
          </div>
        </div>

        {/* Subjects */}
        <div className="grid md:grid-cols-2 gap-6 mb-10">
          {Object.values(subjects).map((s, i) => {
            const ui = SUBJECT_UI[s.name];
            const Icon = ui.icon;

            return (
              <motion.div key={s.name} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
                <div className="bg-white rounded-xl shadow overflow-hidden">
                  <div className={`bg-gradient-to-r ${ui.gradientFrom} ${ui.gradientTo} p-6 text-white`}>
                    <div className="flex items-center gap-3">
                      <Icon className="w-7 h-7" />
                      <h3 className="text-2xl font-bold">{s.name}</h3>
                    </div>
                  </div>

                  <div className="p-6">
                    <p className="mb-4 text-gray-600">{s.description}</p>

                    {s.status === "in_progress" && (
                      <>
                        <Progress value={s.progress} />
                        <button onClick={() => goToAssessment(s.name, true)} className="btn-primary mt-4">
                          <PlayCircle /> Resume Assessment
                        </button>
                      </>
                    )}

                    {s.status === "not_started" && (
                      <button onClick={() => goToAssessment(s.name)} className="btn-primary">
                        <PlayCircle /> Take Assessment
                      </button>
                    )}

                    {s.status === "completed" && (
                      <>
                        <button onClick={() => goToReport(s.assessment_id!)} className="btn-secondary">
                          <FileText /> View Report
                        </button>
                        <button onClick={() => goToCourse(s.name)} className="btn-primary mt-2">
                          <ArrowRight /> Start Course
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Badges */}
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
            <Award /> Your Badges
          </h2>

          <div className="grid grid-cols-4 md:grid-cols-8 gap-4">
            {BADGES.map((b) => {
              const Icon = b.icon;
              return (
                <div key={b.id} className="flex flex-col items-center gap-2">
                  <div
                    className={`w-14 h-14 rounded-full flex items-center justify-center ${
                      b.unlocked
                        ? `bg-gradient-to-br ${BADGE_GRADIENTS[b.color]}`
                        : "bg-gray-300"
                    }`}
                  >
                    {b.unlocked ? <Icon className="text-white" /> : <Lock />}
                  </div>
                  <span className="text-xs text-center">{b.name}</span>
                </div>
              );
            })}
          </div>

          <div className="mt-6 bg-gradient-to-r from-blue-100 to-purple-100 rounded-xl p-4 flex items-center gap-3">
            <Sparkles className="text-purple-600" />
            <div>
              <p className="font-semibold">Keep it up!</p>
              <p className="text-sm text-gray-600">Complete more courses to unlock badges.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
