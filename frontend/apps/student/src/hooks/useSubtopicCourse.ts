import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";
import type {
  SubtopicCourse,
  MarkProgressPayload,
  FeedbackPayload,
  QuizSubmitPayload,
  QuizSubmitResult,
  ChatHistory,
  GradeAnswerPayload,
  GradeAnswerResult,
  TransferQuestion,
} from "../types/miniCourse";

export function useSubtopicCourse(subtopicId: string) {
  return useQuery<SubtopicCourse>({
    queryKey: ["subtopic-course", subtopicId],
    queryFn: async () => {
      const response = await apiClient.get<SubtopicCourse>(
        `/api/v1/students/me/subtopics/${subtopicId}/course`,
      );
      return response.data;
    },
    enabled: !!subtopicId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

export function useMarkCourseProgress(subtopicId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MarkProgressPayload) => {
      const response = await apiClient.post(
        `/api/v1/students/me/subtopics/${subtopicId}/course/progress`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["subtopic-course", subtopicId],
      });
    },
  });
}

export function useSubmitQuiz(subtopicId: string) {
  const queryClient = useQueryClient();
  return useMutation<QuizSubmitResult, Error, QuizSubmitPayload>({
    mutationFn: async (payload) => {
      const response = await apiClient.post<QuizSubmitResult>(
        `/api/v1/students/me/subtopics/${subtopicId}/course/quiz`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["subtopic-course", subtopicId],
      });
      queryClient.invalidateQueries({
        queryKey: ["student", "class-topic-subtopics"],
      });
    },
  });
}

export function useSubmitFeedback(contentId: string) {
  return useMutation({
    mutationFn: async (payload: FeedbackPayload) => {
      const response = await apiClient.post(
        `/api/v1/students/me/subtopic-content/${contentId}/feedback`,
        payload,
      );
      return response.data;
    },
  });
}

export function useChatHistory(subtopicId: string) {
  return useQuery<ChatHistory>({
    queryKey: ["subtopic-chat", subtopicId],
    queryFn: async () => {
      const response = await apiClient.get<ChatHistory>(
        `/api/v1/students/me/subtopics/${subtopicId}/chat`,
      );
      return response.data;
    },
    enabled: !!subtopicId,
    staleTime: 0,
  });
}

export function useStreamChatMessage(subtopicId: string) {
  const queryClient = useQueryClient();
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");

  // Keep token ref in sync so long-running streams always use the latest token
  // even if it refreshes mid-stream.
  const tokenRef = useRef(useAuthStore.getState().accessToken);
  useEffect(() => {
    return useAuthStore.subscribe((state) => {
      tokenRef.current = state.accessToken;
    });
  }, []);

  const stream = useCallback(
    async (
      question: string,
      callbacks: {
        onError?: (msg: string) => void;
      } = {},
    ) => {
      setIsStreaming(true);
      setStreamingContent("");

      const token = tokenRef.current;
      const baseUrl = (import.meta.env.VITE_API_BASE_URL as string) ?? "";

      try {
        const response = await fetch(
          `${baseUrl}/api/v1/students/me/subtopics/${subtopicId}/chat`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ question }),
          },
        );

        if (!response.ok || !response.body) {
          callbacks.onError?.("Something went wrong. Please try again.");
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6);
            try {
              const event = JSON.parse(raw) as
                | { type: "chunk"; delta: string }
                | { type: "done"; messages: ChatHistory["messages"] };

              if (event.type === "chunk") {
                setStreamingContent((prev) => prev + event.delta);
              } else if (event.type === "done") {
                queryClient.setQueryData<ChatHistory>(
                  ["subtopic-chat", subtopicId],
                  { messages: event.messages },
                );
                setStreamingContent("");
              }
            } catch {
              // malformed chunk — skip
            }
          }
        }
      } catch {
        callbacks.onError?.("Something went wrong. Please try again.");
      } finally {
        setIsStreaming(false);
        setStreamingContent("");
      }
    },
    [subtopicId, queryClient],
  );

  return { stream, isStreaming, streamingContent };
}

export function useGenerateTransferQuestion(subtopicId: string) {
  return useMutation<TransferQuestion, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post<TransferQuestion>(
        `/api/v1/students/me/subtopics/${subtopicId}/transfer-question`,
      );
      return response.data;
    },
  });
}

export function useGradeAnswer(subtopicId: string) {
  const queryClient = useQueryClient();
  return useMutation<GradeAnswerResult, Error, GradeAnswerPayload>({
    mutationFn: async (payload: GradeAnswerPayload) => {
      const response = await apiClient.post<GradeAnswerResult>(
        `/api/v1/students/me/subtopics/${subtopicId}/grade-answer`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["subtopic-course", subtopicId],
      });
    },
  });
}
