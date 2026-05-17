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
  id: string;
  explanation_text: string;
  interest_category: string | null;
}

export interface CourseVideo {
  url: string;
  title: string;
}

export interface CourseProgress {
  explanation_accessed: boolean;
  video_accessed: boolean;
  check_questions_score: number | null;
}

export interface NextSubtopic {
  id: string;
  name: string;
}

export interface SubtopicCourse {
  subtopic_id: string;
  subtopic_name: string;
  topic_name: string;
  subject_name: string;
  grade_level: number;
  explanation: CourseExplanation | null;
  video: CourseVideo | null;
  check_questions: CourseQuestion[];
  progress: CourseProgress | null;
  next_subtopic: NextSubtopic | null;
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
