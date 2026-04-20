import { create } from "zustand";

export interface PreviewQuestion {
  question_id: string;
  question_text: string;
  question_type: string; // "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER"
  options: Array<{ key: string; text: string }>;
  correct_answer: string;
  difficulty_level: number;
  subtopic_name: string;
}

export type AssessmentType =
  | "DIAGNOSTIC"
  | "TOPIC_SPECIFIC"
  | "PROGRESS_CHECK"
  | "FINAL";

interface AssessmentWizardState {
  currentStep: 1 | 2 | 3 | 4 | 5;
  classId: string | null;
  className: string | null;
  subjectId: string | null;
  gradeId: string | null;
  curriculumId: string | null;
  assessmentType: AssessmentType | null;
  topicIds: string[];
  questionCount: number;
  difficultyMin: number;
  difficultyMax: number;
  deadline: string | null;
  draftAssessmentId: string | null;
  previewQuestions: PreviewQuestion[];
  // actions
  setStep: (step: 1 | 2 | 3 | 4 | 5) => void;
  setClassId: (
    id: string,
    name: string,
    subjectId: string,
    gradeId: string,
    curriculumId: string,
  ) => void;
  setAssessmentType: (type: AssessmentType) => void;
  setTopicIds: (ids: string[]) => void;
  setQuestionCount: (n: number) => void;
  setDifficulty: (min: number, max: number) => void;
  setDeadline: (date: string | null) => void;
  setDraftAssessment: (id: string, questions: PreviewQuestion[]) => void;
  reset: () => void;
}

const initialState = {
  currentStep: 1 as const,
  classId: null,
  className: null,
  subjectId: null,
  gradeId: null,
  curriculumId: null,
  assessmentType: null,
  topicIds: [],
  questionCount: 10,
  difficultyMin: 1.0,
  difficultyMax: 5.0,
  deadline: null,
  draftAssessmentId: null,
  previewQuestions: [],
};

export const useAssessmentWizard = create<AssessmentWizardState>((set) => ({
  ...initialState,

  setStep: (step) => set({ currentStep: step }),

  setClassId: (id, name, subjectId, gradeId, curriculumId) =>
    set({ classId: id, className: name, subjectId, gradeId, curriculumId }),

  setAssessmentType: (type) => set({ assessmentType: type }),

  setTopicIds: (ids) => set({ topicIds: ids }),

  setQuestionCount: (n) => set({ questionCount: n }),

  setDifficulty: (min, max) => set({ difficultyMin: min, difficultyMax: max }),

  setDeadline: (date) => set({ deadline: date }),

  setDraftAssessment: (id, questions) =>
    set({ draftAssessmentId: id, previewQuestions: questions }),

  reset: () => set(initialState),
}));
