import { useQuestionnaireStore } from "../questionnaireStore";

describe("questionnaireStore", () => {
  beforeEach(() => {
    useQuestionnaireStore.getState().reset();
  });

  test("test_set_answer_when_question_key_provided_then_updates_answer", () => {
    const { setAnswer } = useQuestionnaireStore.getState();
    setAnswer("q1_preferred_medium", "visual");
    expect(useQuestionnaireStore.getState().answers.q1_preferred_medium).toBe("visual");
  });

  test("test_toggle_interest_when_interest_not_present_then_adds_it", () => {
    const { toggleInterest } = useQuestionnaireStore.getState();
    toggleInterest("football");
    expect(useQuestionnaireStore.getState().answers.interests).toContain("football");
  });

  test("test_toggle_interest_when_interest_already_present_then_removes_it", () => {
    const { toggleInterest } = useQuestionnaireStore.getState();
    toggleInterest("football");
    toggleInterest("football");
    expect(useQuestionnaireStore.getState().answers.interests).not.toContain("football");
  });

  test("test_reset_when_called_then_clears_all_answers", () => {
    const store = useQuestionnaireStore.getState();
    store.setAnswer("q1_preferred_medium", "visual");
    store.toggleInterest("football");
    store.reset();
    const { answers } = useQuestionnaireStore.getState();
    expect(answers.q1_preferred_medium).toBeNull();
    expect(answers.interests).toHaveLength(0);
  });

  test("test_store_when_initialized_then_has_no_step_state", () => {
    const storeState = useQuestionnaireStore.getState();
    expect(storeState).not.toHaveProperty("currentStep");
    expect(storeState).not.toHaveProperty("nextStep");
    expect(storeState).not.toHaveProperty("prevStep");
  });
});
