"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Trophy,
  Sparkles,
  Lock,
  FileText,
  ArrowRight,
  PlayCircle,
  Award,
} from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { http } from "@/lib/http";
import { useAuth } from "@/contexts/AuthContext";
import { Child } from "@/types";

import {
  AssessmentStatus,
  ICON_MAP,
  GRADIENT_MAP,
} from "@/config/childDashboard";

/* ---------------------------------- */
/* Types (API-driven) */
/* ---------------------------------- */

interface Subject {
  id: string;
  name: string;
  code?: string;
  icon?: string;
  gradient_key?: string;
}

interface SubjectData {
  subject: Subject;
  status: AssessmentStatus;
  description: string;
  assessment_id?: number;
  progress?: number;
  level?: string;
}

interface Badge {
  id: string;
  name: string;
  icon: string;
  color_key: string;
  unlocked: boolean;
}

/* ---------------------------------- */
/* Component */
/* ---------------------------------- */

export const ChildDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [subjects, setSubjects] = useState<SubjectData[]>([]);
  const [badges, setBadges] = useState<Badge[]>([]);

  /* ---------------------------------- */
  /* Navigation */
  /* ---------------------------------- */

  const goToAssessment = (subjectId: string, resume = false) => {
    navigate(
      `/child-dashboard/assessment?subject_id=${subjectId}${
        resume ? "&resume=true" : ""
      }`
    );
  };

  const goToReport = (assessmentId: number) => {
    navigate(
      `/child-dashboard/assessment-diagnostic-report?assessmentId=${assessmentId}`
    );
  };

  const goToCourse = (subjectId: string) => {
    navigate(`/child-dashboard/take-micro-course?subject_id=${subjectId}`);
  };

  /* ---------------------------------- */
  /* Fetch data */
  /* ---------------------------------- */

  useEffect(() => {
    if (!user?.student_profile?.registration_completed_at) {
      navigate("/complete-profile");
      return;
    }

    if (!user?.student_profile?.id) return;

    const fetchDashboardData = async () => {
      try {
        const [subjectsRes, badgesRes] = await Promise.all([
          http.get(`/api/v1/students/${user.student_profile.id}/subjects`,
          ),
          http.get(`/api/v1/students/${user.student_profile.id}/badges`),
        ]);

        setSubjects(subjectsRes.data);
        setBadges(badgesRes.data);
      } catch (err) {
        console.error("Failed to load child dashboard", err);
      }
    };

    fetchDashboardData();
  }, [user?.student_profile?.id, navigate]);

  /* ---------------------------------- */
  /* Render */
  /* ---------------------------------- */

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      <div className="max-w-7xl mx-auto p-6">

        {/* Header */}
        <div className="bg-white rounded-xl shadow p-6 mb-8 flex justify-between">
          <div>
            <h1 className="text-3xl font-bold">
              Welcome back, {user.full_name}!
            </h1>
            <p className="text-gray-600">
              Grade {user.student_profile?.grade.level}
            </p>
          </div>
          <div className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 py-2 rounded-full">
            <Trophy className="w-5 h-5" />
            {badges.length === 0 ? "No badges yet" : `${badges.filter((b) => b.unlocked).length} Badges Earned`}

          </div>
        </div>

        {/* Subjects */}
        <div className="grid md:grid-cols-2 gap-6 mb-10">
          {subjects.map((s) => {
            const Icon =
              (s.subject.icon && ICON_MAP[s.subject.icon]) ?? Award;
            const gradient =
              (s.subject.gradient_key &&
                GRADIENT_MAP[s.subject.gradient_key]) ??
              "from-gray-400 to-gray-600";

            return (
              <motion.div
                key={s.subject.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="bg-white rounded-xl shadow overflow-hidden">
                  <div
                    className={`bg-gradient-to-r ${gradient} p-6 text-white`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-7 h-7" />
                      <h3 className="text-2xl font-bold">
                        {s.subject.name}
                      </h3>
                    </div>
                  </div>

                  <div className="p-6">
                    <p className="mb-4 text-gray-600">{s.description}</p>

                    {s.status === "in_progress" && (
                      <>
                        <Progress value={s.progress} />
                        <button
                          onClick={() =>
                            goToAssessment(s.subject.id, true)
                          }
                          className="btn-primary mt-4"
                        >
                          <PlayCircle /> Resume Assessment
                        </button>
                      </>
                    )}

                    {s.status === "not_started" && (
                      <button
                        onClick={() =>
                          goToAssessment(s.subject.id)
                        }
                        className="btn-primary"
                      >
                        <PlayCircle /> Take Assessment
                      </button>
                    )}

                    {s.status === "completed" && (
                      <>
                        <button
                          onClick={() => goToReport(s.assessment_id!)}
                          className="btn-secondary"
                        >
                          <FileText /> View Report
                        </button>
                        <button
                          onClick={() => goToCourse(s.subject.id)}
                          className="btn-primary mt-2"
                        >
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
            {badges.map((b) => {
              const Icon = ICON_MAP[b.icon] ?? Award;
              const gradient =
                GRADIENT_MAP[b.color_key] ?? "from-gray-400 to-gray-600";

              return (
                <div
                  key={b.id}
                  className="flex flex-col items-center gap-2"
                >
                  <div
                    className={`w-14 h-14 rounded-full flex items-center justify-center ${
                      b.unlocked
                        ? `bg-gradient-to-br ${gradient}`
                        : "bg-gray-300"
                    }`}
                  >
                    {b.unlocked ? (
                      <Icon className="text-white" />
                    ) : (
                      <Lock />
                    )}
                  </div>
                  <span className="text-xs text-center">
                    {b.name}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="mt-6 bg-gradient-to-r from-blue-100 to-purple-100 rounded-xl p-4 flex items-center gap-3">
            <Sparkles className="text-purple-600" />
            <div>
              <p className="font-semibold">Keep it up!</p>
              <p className="text-sm text-gray-600">
                Complete more courses to unlock badges.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
