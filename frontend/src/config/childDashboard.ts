import {
  BookOpen,
  Beaker,
  Edit3,
  Globe2,
  Trophy,
  Star,
  Zap,
  Target,
  Award,
  Sparkles,
} from "lucide-react";

export type Subject = "Math" | "Science" | "English" | "Humanities";

export type AssessmentStatus = "not_started" | "in_progress" | "completed";

export interface SubjectUIConfig {
  icon: any;
  color: string;
  gradientFrom: string;
  gradientTo: string;
}

export const SUBJECT_UI: Record<Subject, SubjectUIConfig> = {
  Math: {
    icon: BookOpen,
    color: "blue",
    gradientFrom: "from-blue-500",
    gradientTo: "to-cyan-500",
  },
  English: {
    icon: Edit3,
    color: "purple",
    gradientFrom: "from-purple-500",
    gradientTo: "to-pink-500",
  },
  Science: {
    icon: Beaker,
    color: "emerald",
    gradientFrom: "from-emerald-500",
    gradientTo: "to-teal-500",
  },
  Humanities: {
    icon: Globe2,
    color: "orange",
    gradientFrom: "from-orange-500",
    gradientTo: "to-red-500",
  },
};

export const BADGES = [
  { id: "1", name: "Quick Starter", icon: Zap, unlocked: true, color: "yellow" },
  { id: "2", name: "First Steps", icon: Star, unlocked: true, color: "blue" },
  { id: "3", name: "Math Master", icon: Trophy, unlocked: false, color: "purple" },
  { id: "4", name: "Science Explorer", icon: Beaker, unlocked: true, color: "green" },
  { id: "5", name: "Reading Champion", icon: BookOpen, unlocked: false, color: "pink" },
  { id: "6", name: "Goal Achiever", icon: Target, unlocked: false, color: "orange" },
  { id: "7", name: "Perfect Score", icon: Award, unlocked: false, color: "red" },
  { id: "8", name: "Creative Thinker", icon: Sparkles, unlocked: false, color: "indigo" },
];

export const BADGE_GRADIENTS: Record<string, string> = {
  yellow: "from-yellow-400 to-yellow-600",
  blue: "from-blue-400 to-blue-600",
  purple: "from-purple-400 to-purple-600",
  green: "from-green-400 to-green-600",
  pink: "from-pink-400 to-pink-600",
  orange: "from-orange-400 to-orange-600",
  red: "from-red-400 to-red-600",
  indigo: "from-indigo-400 to-indigo-600",
};
