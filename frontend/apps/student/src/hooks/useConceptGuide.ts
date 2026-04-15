import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface ConceptGuideRequest {
  subtopicId: string;
  question?: string;
}

interface ConceptGuideResponse {
  explanation: string;
  subtopicName: string;
}

async function fetchConceptGuide(
  req: ConceptGuideRequest,
): Promise<ConceptGuideResponse> {
  const res = await apiClient.post<ConceptGuideResponse>(
    "/api/v1/students/me/concept-guide",
    {
      subtopic_id: req.subtopicId,
      question: req.question ?? null,
    },
  );
  return res.data;
}

export function useConceptGuide() {
  return useMutation<ConceptGuideResponse, Error, ConceptGuideRequest>({
    mutationFn: fetchConceptGuide,
  });
}
