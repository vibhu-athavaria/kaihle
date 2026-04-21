import { useEffect } from "react";
import { X } from "lucide-react";
import { useConceptGuideContext } from "../../context/ConceptGuideContext";
import { ConceptGuidePanelContent } from "../my-progress/ConceptGuidePanel";

export function ConceptGuideDrawer() {
  const { state, closeGuide } = useConceptGuideContext();
  const { isOpen, subtopicId, subtopicName, masteryScore } = state;

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeGuide();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, closeGuide]);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/10"
          onClick={closeGuide}
          aria-hidden="true"
        />
      )}

      <div
        role="dialog"
        aria-modal="true"
        aria-label={`AI concept guide for ${subtopicName ?? "subtopic"}`}
        className={`fixed top-0 right-0 h-full w-[360px] z-50 bg-white border-l border-brand-border shadow-lg flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-brand-border flex-shrink-0">
          <div>
            <span className="font-sans text-xs font-bold uppercase tracking-widest text-brand-primary">
              AI Concept Guide
            </span>
            {subtopicName && (
              <p className="font-sans text-sm font-semibold text-brand-ink mt-0.5 truncate max-w-[280px]">
                {subtopicName}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={closeGuide}
            className="text-brand-muted hover:text-brand-ink transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
            aria-label="Close concept guide"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isOpen && subtopicId && subtopicName ? (
            <ConceptGuidePanelContent
              subtopicId={subtopicId}
              subtopicName={subtopicName}
              masteryScore={masteryScore}
              onClose={closeGuide}
            />
          ) : null}
        </div>
      </div>
    </>
  );
}
