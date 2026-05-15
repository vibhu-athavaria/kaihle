import { useQuestionnaireStore } from "../questionnaireStore";

describe("questionnaireStore", () => {
  beforeEach(() => {
    useQuestionnaireStore.getState().reset();
  });

  test("test_set_answer_when_question_id_provided_then_updates_answer", () => {
    const { setAnswer } = useQuestionnaireStore.getState();
    setAnswer("q1", "watch_walkthrough");
    expect(useQuestionnaireStore.getState().answers["q1"]).toBe(
      "watch_walkthrough",
    );
  });

  test("test_set_answer_when_multiple_questions_answered_then_each_stored_independently", () => {
    const { setAnswer } = useQuestionnaireStore.getState();
    setAnswer("q1", "watch_walkthrough");
    setAnswer("q6", "sports_movement");
    setAnswer("q7", "paces");
    const { answers } = useQuestionnaireStore.getState();
    expect(answers["q1"]).toBe("watch_walkthrough");
    expect(answers["q6"]).toBe("sports_movement");
    expect(answers["q7"]).toBe("paces");
  });

  test("test_set_answer_when_answer_overwritten_then_latest_value_stored", () => {
    const { setAnswer } = useQuestionnaireStore.getState();
    setAnswer("q1", "watch_walkthrough");
    setAnswer("q1", "read_explanation");
    expect(useQuestionnaireStore.getState().answers["q1"]).toBe(
      "read_explanation",
    );
  });

  test("test_reset_when_called_then_clears_all_answers", () => {
    const store = useQuestionnaireStore.getState();
    store.setAnswer("q1", "watch_walkthrough");
    store.setAnswer("q6", "sports_movement");
    store.reset();
    const { answers } = useQuestionnaireStore.getState();
    expect(Object.keys(answers)).toHaveLength(0);
  });

  test("test_store_when_initialized_then_has_no_step_state", () => {
    const storeState = useQuestionnaireStore.getState();
    expect(storeState).not.toHaveProperty("currentStep");
    expect(storeState).not.toHaveProperty("nextStep");
    expect(storeState).not.toHaveProperty("prevStep");
  });
});
