import { create } from "zustand";

export interface QuestionnaireAnswers {
  // Keyed by question ID (e.g. "q1", "q2", ...) — works for any questionnaire version
  [questionId: string]: string | null;
}

interface QuestionnaireState {
  answers: QuestionnaireAnswers;
  setAnswer: (questionId: string, value: string) => void;
  reset: () => void;
}

export const useQuestionnaireStore = create<QuestionnaireState>((set) => ({
  answers: {},
  setAnswer: (questionId, value) =>
    set((state) => ({
      answers: { ...state.answers, [questionId]: value },
    })),
  reset: () => set({ answers: {} }),
}));
