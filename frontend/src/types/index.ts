export type UserRole = "parent" | "student" | "teacher" | "admin" | "school_admin" | "super_admin";

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  role: UserRole;
  created_at: string;
  has_completed_assessment?: boolean;
  student_profile?: {
    id: string;
    registration_completed_at: Date | null;
  };
}

export interface Child {
  id: string
  parent_id: string
  age: number | null
  grade_level: string | null
  interests: string[] | null
  preferred_format: string | null
  preferred_session_length: number | null
  registration_completed_at: Date | null
  user: {
    full_name: string
    username: string
    email: string | null
    role: UserRole
    has_completed_assessment: boolean
  }
}

export interface Lesson {
  id: string;
  title: string;
  subject: string;
  icon: string;
  type: 'today' | 'upcoming';
  schedule?: string;
  child_id: string;
}

export interface ChatMessage {
  id: string;
  message: string;
  is_user: boolean;
  timestamp: string;
  child_id: string;
}

export interface AuthContextType {
  user: User | null;
  signUpParent: (email: string, password: string, full_name: string) => Promise<void>;
  signInParent: (email: string, password: string) => Promise<void>;
  signInStudent: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  loading: boolean;
}

export enum AssessmentType {
  DIAGNOSTIC = "diagnostic",
  PROGRESS = "progress",
  FINAL = "final",
  TOPIC_SPECIFIC = "topic_specific"
}

export enum AssessmentStatus{
  NOT_STARTED = "not_started",
  STARTED = "started",
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
  ABANDONED = "abandoned"
}
