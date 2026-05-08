/**
 * TypeScript interfaces for AI-generated lesson plan content.
 * Mirrors the backend LessonPlanContent Pydantic schema exactly.
 */

export interface LessonPlanMisconception {
  student_error: string;
  trigger_phrase: string;
  recovery_script: string;
}

export interface LessonPlanConcept {
  name: string;
  duration_minutes: number;
  teacher_does: string;
  student_does: string;
  check_question: string;
  misconception: LessonPlanMisconception;
  transition_cue: string | null;
}

export interface LessonPlanGroupActivity {
  description: string;
  stuck_prompt: string;
}

export interface LessonPlanExitTicketQuestion {
  label: string;
  question_text: string;
  good_answer: string;
  pivot_if_wrong: string;
}

export interface LessonPlanContent {
  lesson_hook: string;
  time_breakdown: {
    starter_minutes: number;
    intro_minutes: number;
    activity_minutes: number;
    exit_ticket_minutes: number;
    plenary_minutes: number;
  };
  learning_objectives: string[];
  key_concepts: LessonPlanConcept[];
  group_activities: {
    foundation: LessonPlanGroupActivity;
    core: LessonPlanGroupActivity;
    extension: LessonPlanGroupActivity;
  };
  resources_needed: string[];
  exit_ticket: {
    questions: LessonPlanExitTicketQuestion[];
  };
  starter: { duration_minutes: number; activity: string };
  plenary: { duration_minutes: number; activity: string };
  prior_knowledge: string;
  homework: string | null;
}

export interface ClassContextSnapshot {
  modality_distribution: Record<string, number>;
  top_interests: string[];
  student_count: number;
}
