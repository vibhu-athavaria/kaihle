import { useState, useRef, useEffect } from "react";
import { X, Send, AlertCircle, Bot, User } from "lucide-react";
import {
  useChatHistory,
  useStreamChatMessage,
} from "../../hooks/useSubtopicCourse";

export interface ExplainThisDrawerProps {
  open: boolean;
  onClose: () => void;
  subtopicId: string;
  subtopicName: string;
  initialQuestion?: string;
}

export function ExplainThisDrawer({
  open,
  onClose,
  subtopicId,
  subtopicName,
  initialQuestion,
}: ExplainThisDrawerProps) {
  const [question, setQuestion] = useState(initialQuestion ?? "");
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<Element | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  const { data: chatHistory, isFetching: historyLoading } =
    useChatHistory(subtopicId);
  const { stream, isStreaming, streamingContent } =
    useStreamChatMessage(subtopicId);

  // Pre-fill question when initialQuestion changes (e.g. from "Ask AI tutor" in quiz)
  useEffect(() => {
    if (initialQuestion) setQuestion(initialQuestion);
  }, [initialQuestion]);

  // Scroll to bottom on new messages or streaming content change
  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatHistory?.messages.length, streamingContent, open]);

  // Capture trigger element on open so focus can return on close
  useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement;
    } else {
      (triggerRef.current as HTMLElement | null)?.focus();
      triggerRef.current = null;
    }
  }, [open]);

  // Focus trap
  useEffect(() => {
    if (!open) return;
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

  const handleSend = () => {
    const q = question.trim();
    if (!q || isStreaming) return;

    setSendError(null);
    setQuestion(""); // clear immediately — don't wait for the stream to finish
    stream(q, {
      onError: (msg) => setSendError(msg),
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      handleSend();
    }
  };

  if (!open) return null;

  const messages = chatHistory?.messages ?? [];

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
        aria-label={`AI Tutor — ${subtopicName}`}
        className="relative w-[420px] max-w-[90vw] h-full bg-white shadow-xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-brand-border flex-shrink-0">
          <div>
            <h2 className="font-display font-bold text-lg text-brand-ink leading-tight">
              AI Tutor
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

        {/* Message thread */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {historyLoading && messages.length === 0 && (
            <div className="space-y-3 animate-pulse">
              <div className="h-10 bg-brand-border rounded-xl w-4/5" />
              <div className="h-16 bg-brand-border rounded-xl w-4/5 ml-auto" />
            </div>
          )}

          {!historyLoading && messages.length === 0 && (
            <div className="text-center py-10">
              <Bot
                className="w-8 h-8 text-brand-muted mx-auto mb-2"
                aria-hidden="true"
              />
              <p className="font-sans text-sm text-brand-muted">
                Ask me anything about <strong>{subtopicName}</strong>
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.created_at}
              className={`flex gap-2.5 ${msg.role === "student" ? "flex-row-reverse" : ""}`}
            >
              <div
                className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                  msg.role === "ai" ? "bg-brand-primary/10" : "bg-brand-border"
                }`}
              >
                {msg.role === "ai" ? (
                  <Bot
                    className="w-4 h-4 text-brand-primary"
                    aria-hidden="true"
                  />
                ) : (
                  <User
                    className="w-4 h-4 text-brand-muted"
                    aria-hidden="true"
                  />
                )}
              </div>
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 font-sans text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "ai"
                    ? "bg-brand-primary/5 text-brand-ink rounded-tl-sm"
                    : "bg-brand-ink text-white rounded-tr-sm"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {/* Streaming AI reply — shows live text while generating, replaced by persisted message on done */}
          {isStreaming && (
            <div className="flex gap-2.5">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-brand-primary/10 flex items-center justify-center">
                <Bot
                  className="w-4 h-4 text-brand-primary"
                  aria-hidden="true"
                />
              </div>
              <div className="max-w-[80%] bg-brand-primary/5 rounded-2xl rounded-tl-sm px-4 py-3 font-sans text-sm leading-relaxed text-brand-ink whitespace-pre-wrap">
                {streamingContent || (
                  <span className="flex gap-1">
                    {[0, 150, 300].map((delay) => (
                      <span
                        key={delay}
                        className="inline-block w-1.5 h-1.5 rounded-full bg-brand-primary animate-bounce"
                        style={{ animationDelay: `${delay}ms` }}
                      />
                    ))}
                  </span>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error */}
        {sendError && (
          <div className="mx-5 mb-2 flex items-center gap-2 text-red-600 bg-red-50 rounded-xl p-3">
            <AlertCircle className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            <p className="font-sans text-sm">{sendError}</p>
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-brand-border px-5 py-4 flex-shrink-0">
          <div className="flex gap-2 items-end">
            <textarea
              aria-label="Your question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={500}
              rows={2}
              placeholder="Ask a question… (Ctrl+Enter to send)"
              className="flex-1 rounded-xl border border-brand-border p-3 font-sans text-sm text-brand-ink placeholder-brand-muted resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            />
            <button
              onClick={handleSend}
              disabled={!question.trim() || isStreaming}
              aria-label="Send message"
              className="flex-shrink-0 w-10 h-10 rounded-full bg-brand-primary text-white flex items-center justify-center hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
          <p className="font-sans text-xs text-brand-muted mt-1 text-right">
            {question.length} / 500
          </p>
        </div>
      </div>
    </div>
  );
}
