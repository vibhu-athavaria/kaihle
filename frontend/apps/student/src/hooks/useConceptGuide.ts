import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface CheckQuestion {
  question: string;
  options: string[];
  correct: string;
}

interface ConceptGuideRequest {
  subtopicId: string;
  question?: string;
}

interface ConceptGuideResponse {
  explanation: string;
  subtopicName: string;
  checkQuestion: CheckQuestion | null;
}

interface McqAnswerRequest {
  subtopicName: string;
  question: string;
  options: string[];
  correct: string;
  studentAnswer: string;
}

interface McqAnswerResponse {
  isCorrect: boolean;
  response: string;
}

async function fetchConceptGuide(
  req: ConceptGuideRequest,
): Promise<ConceptGuideResponse> {
  const res = await apiClient.post<{
    explanation: string;
    subtopic_name: string;
    check_question: CheckQuestion | null;
  }>("/api/v1/students/me/concept-guide", {
    subtopic_id: req.subtopicId,
    question: req.question ?? null,
  });
  return {
    explanation: res.data.explanation,
    subtopicName: res.data.subtopic_name,
    checkQuestion: res.data.check_question,
  };
}

async function submitMcqAnswer(
  req: McqAnswerRequest,
): Promise<McqAnswerResponse> {
  const res = await apiClient.post<{ is_correct: boolean; response: string }>(
    "/api/v1/students/me/concept-guide/answer",
    {
      subtopic_name: req.subtopicName,
      question: req.question,
      options: req.options,
      correct: req.correct,
      student_answer: req.studentAnswer,
    },
  );
  return {
    isCorrect: res.data.is_correct,
    response: res.data.response,
  };
}

export function useConceptGuide() {
  return useMutation<ConceptGuideResponse, Error, ConceptGuideRequest>({
    mutationFn: fetchConceptGuide,
  });
}

export function useMcqAnswer() {
  return useMutation<McqAnswerResponse, Error, McqAnswerRequest>({
    mutationFn: submitMcqAnswer,
  });
}
