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

// export type Subject = "Math" | "Science" | "English" | "Humanities";

export type AssessmentStatus = "not_started" | "in_progress" | "completed";

export interface Subject {
  id: string;
  name: string;
  code?: string;
  icon?: string;
  color?: string;
  gradient_key?: string;
}

export const ICON_MAP: Record<string, any> = {
  "book-open": BookOpen,
  "beaker": Beaker,
  "edit-3": Edit3,
  "globe": Globe2,
  "trophy": Trophy,
  "star": Star,
  "zap": Zap,
  "target": Target,
  "award": Award,
  "sparkles": Sparkles,
};

export const GRADIENT_MAP: Record<string, string> = {
  yellow: "from-yellow-400 to-yellow-600",
  blue: "from-blue-400 to-blue-600",
  purple: "from-purple-400 to-purple-600",
  green: "from-green-400 to-green-600",
  pink: "from-pink-400 to-pink-600",
  orange: "from-orange-400 to-orange-600",
  red: "from-red-400 to-red-600",
  indigo: "from-indigo-400 to-indigo-600",
};


export interface Badge {
  id: string;
  name: string;
  description?: string;
  icon: string;        // key from backend
  color_key: string;   // key from backend
  points_required: number;
  unlocked: boolean;
}

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

// export const BADGE_GRADIENTS: Record<string, string> = {
//   yellow: "from-yellow-400 to-yellow-600",
//   blue: "from-blue-400 to-blue-600",
//   purple: "from-purple-400 to-purple-600",
//   green: "from-green-400 to-green-600",
//   pink: "from-pink-400 to-pink-600",
//   orange: "from-orange-400 to-orange-600",
//   red: "from-red-400 to-red-600",
//   indigo: "from-indigo-400 to-indigo-600",
// };
