export type IntakeForm = {
  form_id: string;
  target_age_range: string;
  sections: IntakeSection[];
};

export type IntakeSection = {
  section_id: string;
  title: string;
  description?: string;
  questions: IntakeQuestion[];
};

export type IntakeQuestion = {
  question_id: string;
  type: "single_select" | "multi_select";
  label: string;
  max_selections?: number;
  options: IntakeOption[];
};

export type IntakeOption = {
  value: string;
  label: string;
};

/**
 * Answers keyed by question_id
 * - single_select → string
 * - multi_select → string[]
 */
export type IntakeAnswers = Record<string, string | string[]>;
