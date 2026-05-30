// Mirrors LearningProfileItem in backend/app/schemas/mini_course.py — keep in sync.
export interface LearningProfileItem {
  dominant_modality: string | null;
  interest: string | null;
  work_style_label: string | null;
}

export interface LatestOpenAnswer {
  question_text: string;
  student_answer: string;
  ai_grade: string | null;
  ai_feedback: string | null;
  score: number;
}

export interface ChatMessage {
  role: "student" | "ai";
  content: string;
  created_at: string;
}

export interface ChatHistory {
  messages: ChatMessage[];
}

export interface TransferQuestion {
  question_text: string;
}

export interface GradeAnswerPayload {
  question_text: string;
  student_answer: string;
}

export interface GradeAnswerResult {
  grade: "correct" | "partial" | "incorrect";
  feedback: string;
  score: number;
  updated_course_score: number | null;
}

export interface CourseOption {
  key: string;
  text: string;
}

export interface CourseQuestion {
  question_id: string;
  question_text: string;
  options: CourseOption[];
  correct_answer: string;
}

export interface CourseExplanation {
  content_id: string;
  explanation_text: string;
  interest_matched: boolean;
}

export interface CourseVideo {
  video_url: string;
  thumbnail_url: string | null;
  duration_seconds: number | null;
}

export interface CourseProgress {
  explanation_accessed: boolean;
  video_accessed: boolean;
  check_questions_score: number | null;
  last_visited_at: string | null;
}

export interface NextSubtopic {
  id: string;
  name: string;
}

export interface SubtopicCourse {
  subtopic_id: string;
  subtopic_name: string;
  topic_name: string;
  explanation: CourseExplanation | null;
  content_status: "ready" | "unavailable";
  video: CourseVideo | null;
  check_questions: CourseQuestion[];
  progress: CourseProgress;
  next_subtopic: NextSubtopic | null;
  learning_profile: LearningProfileItem | null;
  latest_open_answer: LatestOpenAnswer | null;
}

export interface MarkProgressPayload {
  explanation_accessed?: boolean;
  video_accessed?: boolean;
}

export interface FeedbackPayload {
  feedback_type: "thumbs_up" | "thumbs_down";
  comment?: string;
}

export interface QuizAnswerItem {
  question_id: string;
  selected_key: string;
}

export interface QuizSubmitPayload {
  answers: QuizAnswerItem[];
}

export interface QuizSubmitResult {
  score: number;
  correct: number;
  total: number;
  status: "not_started" | "in_progress" | "completed";
}
