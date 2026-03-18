import { create } from "zustand";
// Mapping from API question IDs to store answer keys
export const QUESTION_KEYS = [
    "q1_preferred_medium",
    "q2_learning_pace",
    "q3_help_preference",
    "q4_environment",
    "q5_goal",
];
const initialAnswers = {
    q1_preferred_medium: null,
    q2_learning_pace: null,
    q3_help_preference: null,
    q4_environment: null,
    q5_goal: null,
    interests: [],
};
export const useQuestionnaireStore = create((set) => ({
    answers: { ...initialAnswers },
    currentStep: 1,
    setAnswer: (question, value) => set((state) => ({
        answers: { ...state.answers, [question]: value },
    })),
    toggleInterest: (interest) => set((state) => {
        const current = state.answers.interests;
        const updated = current.includes(interest)
            ? current.filter((i) => i !== interest)
            : [...current, interest];
        return { answers: { ...state.answers, interests: updated } };
    }),
    nextStep: () => set((state) => ({ currentStep: Math.min(state.currentStep + 1, 6) })),
    prevStep: () => set((state) => ({ currentStep: Math.max(state.currentStep - 1, 1) })),
    reset: () => set({ answers: { ...initialAnswers }, currentStep: 1 }),
}));
