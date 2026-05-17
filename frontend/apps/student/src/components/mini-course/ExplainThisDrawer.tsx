import { useState, useRef, useCallback, useEffect } from "react";
import { X, Send, AlertCircle } from "lucide-react";
import { useAuthStore } from "@kaihle/auth";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface ExplainThisDrawerProps {
  open: boolean;
  onClose: () => void;
  subtopicId: string;
  subtopicName: string;
}

export function ExplainThisDrawer({
  open,
  onClose,
  subtopicId,
  subtopicName,
}: ExplainThisDrawerProps) {
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [answer, setAnswer] = useState("");
  const [streamError, setStreamError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const accessToken = useAuthStore((s) => s.accessToken);
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Focus trap
  useEffect(() => {
    if (!open) return;

    // Focus close button on open
    closeButtonRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }

      if (e.key !== "Tab") return;

      const drawer = drawerRef.current;
      if (!drawer) return;

      const focusableSelectors =
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
      const focusable = Array.from(
        drawer.querySelectorAll<HTMLElement>(focusableSelectors),
      ).filter((el) => !el.closest("[hidden]"));

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // Abort stream on close
  useEffect(() => {
    if (!open) {
      abortRef.current?.abort();
      setQuestion("");
      setAnswer("");
      setStreamError(null);
      setStreaming(false);
    }
  }, [open]);

  const handleAsk = useCallback(async () => {
    if (!question.trim() || streaming) return;

    setAnswer("");
    setStreamError(null);
    setStreaming(true);

    abortRef.current = new AbortController();

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/students/me/subtopics/${subtopicId}/explain`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({ question: question.trim() }),
          signal: abortRef.current.signal,
        },
      );

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") break;
            setAnswer((prev) => prev + data);
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // drawer closed — silent
      } else {
        setStreamError("Something went wrong. Try again.");
      }
    } finally {
      setStreaming(false);
    }
  }, [question, streaming, subtopicId, accessToken]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      void handleAsk();
    }
  };

  const handleAskAnother = () => {
    setQuestion("");
    setAnswer("");
    setStreamError(null);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Ask about "${subtopicName}"`}
        className="relative w-[400px] max-w-[90vw] h-full bg-white shadow-xl flex flex-col animate-slide-in-right"
        style={{ transform: "translateX(0)" }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-brand-border flex-shrink-0">
          <div>
            <h2 className="font-display font-bold text-lg text-brand-ink leading-tight">
              Explain This
            </h2>
            <p className="font-sans text-xs text-brand-muted mt-0.5 line-clamp-1">
              {subtopicName}
            </p>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Close"
            className="flex-shrink-0 p-1.5 rounded-lg text-brand-muted hover:text-brand-ink hover:bg-gray-100 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
          {/* Textarea */}
          <div>
            <label
              htmlFor="drawer-explain-question"
              className="font-sans text-sm font-semibold text-brand-ink mb-1.5 block"
            >
              Ask a question about{" "}
              <span className="text-brand-primary">{subtopicName}</span>
            </label>
            <textarea
              id="drawer-explain-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={500}
              rows={4}
              placeholder={`E.g. Can you explain this with a real-life example?`}
              className="w-full rounded-xl border border-brand-border p-3 font-sans text-sm text-brand-ink placeholder-brand-muted resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            />
            <p className="font-sans text-xs text-brand-muted text-right mt-1">
              {question.length} / 500
            </p>
          </div>

          {/* Ask button */}
          <button
            onClick={() => void handleAsk()}
            disabled={!question.trim() || streaming}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-primary text-white rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" aria-hidden="true" />
            {streaming ? "Thinking..." : "Ask"}
          </button>

          {/* Error */}
          {streamError && (
            <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-xl p-3">
              <AlertCircle
                className="w-4 h-4 flex-shrink-0"
                aria-hidden="true"
              />
              <p className="font-sans text-sm">{streamError}</p>
            </div>
          )}

          {/* Answer area */}
          {(answer || streaming) && (
            <div className="bg-brand-primary/5 rounded-xl p-4 border border-brand-primary/20">
              <p className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-2">
                Answer
              </p>
              <p className="font-sans text-sm text-brand-ink leading-relaxed whitespace-pre-wrap">
                {answer}
                {streaming && (
                  <span
                    className="inline-block w-[2px] h-4 bg-brand-primary ml-0.5 animate-pulse align-middle"
                    aria-hidden="true"
                  />
                )}
              </p>
            </div>
          )}

          {/* Ask another */}
          {answer && !streaming && (
            <button
              onClick={handleAskAnother}
              className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
            >
              Ask another question →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
