# ST-D — Concept Guide: Right-Side Sliding Panel
Executor: Coding agent
Branch: `st-d-concept-guide-panel` (branch from `main`)

---

## Context

The AI Concept Guide exists today as an inline collapsing component (`ConceptGuidePanel.tsx`) inside `SubtopicScoreRow`. The hooks `useConceptGuide` and `useMcqAnswer` are production-ready and call real LLM endpoints.

This task replaces the inline component with a right-side sliding panel that:
- Opens when a student clicks "Explain this →" on any subtopic row in My Progress
- Overlays the page content (does not push layout)
- Is a single-session interaction: student reads explanation, tries MCQ, closes panel
- No chat history is stored (MVP scope)
- Panel is designed to be extended to multi-turn in a future sprint — the data shape must support this even though history is not used now

The panel is accessible from My Progress only in this sprint. Study Plans integration comes after ST-C is merged.

---

## Files to Create

- `src/components/ai/ConceptGuideDrawer.tsx` — the drawer shell (slide-in panel)
- `src/context/ConceptGuideContext.tsx` — lightweight context to open/close the panel from anywhere

## Files to Modify

- `src/components/my-progress/ConceptGuidePanel.tsx` — adapt content to work inside the drawer
- `src/components/my-progress/SubtopicScoreRow.tsx` — trigger drawer instead of inline panel
- `src/pages/my-progress/MyProgress.tsx` — wrap page with ConceptGuideProvider, render drawer
- `src/App.tsx` — no changes needed (drawer is page-level, not route-level)

---

## Data Shape (design for future, build for MVP)

Define this interface at the top of `ConceptGuideContext.tsx`. This is the shape that will carry conversation history when multi-turn ships. For MVP, `exchanges` always has 0 or 1 entries.

```ts
interface ConceptSession {
  subtopicId: string;
  subtopicName: string;
  masteryScore: number | null;
  // Designed for multi-turn. MVP: always 0 or 1 entries.
  exchanges: Array<{
    role: "ai" | "student";
    content: string;
  }>;
  mcqResult: "correct" | "incorrect" | null;
  closedAt: Date | null;
}
```

---

## Task 1 — ConceptGuideContext

**File:** `src/context/ConceptGuideContext.tsx`

```tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface ConceptGuideState {
  isOpen: boolean;
  subtopicId: string | null;
  subtopicName: string | null;
  masteryScore: number | null;
}

interface ConceptGuideContextValue {
  state: ConceptGuideState;
  openGuide: (params: { subtopicId: string; subtopicName: string; masteryScore: number | null }) => void;
  closeGuide: () => void;
}

const ConceptGuideContext = createContext<ConceptGuideContextValue | null>(null);

const CLOSED_STATE: ConceptGuideState = {
  isOpen: false,
  subtopicId: null,
  subtopicName: null,
  masteryScore: null,
};

export function ConceptGuideProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConceptGuideState>(CLOSED_STATE);

  const openGuide = useCallback(
    (params: { subtopicId: string; subtopicName: string; masteryScore: number | null }) => {
      setState({ isOpen: true, ...params });
    },
    [],
  );

  const closeGuide = useCallback(() => {
    setState(CLOSED_STATE);
  }, []);

  return (
    <ConceptGuideContext.Provider value={{ state, openGuide, closeGuide }}>
      {children}
    </ConceptGuideContext.Provider>
  );
}

export function useConceptGuideContext(): ConceptGuideContextValue {
  const ctx = useContext(ConceptGuideContext);
  if (!ctx) {
    throw new Error("useConceptGuideContext must be used within ConceptGuideProvider");
  }
  return ctx;
}
```

---

## Task 2 — ConceptGuideDrawer shell

**File:** `src/components/ai/ConceptGuideDrawer.tsx`

The drawer is a fixed-position panel on the right side of the viewport. It slides in using CSS transform. It renders a backdrop scrim behind it. It does not push the main content — it overlays it.

```tsx
import { useEffect } from "react";
import { X } from "lucide-react";
import { useConceptGuideContext } from "../../context/ConceptGuideContext";
import { ConceptGuidePanelContent } from "../my-progress/ConceptGuidePanel";

export function ConceptGuideDrawer() {
  const { state, closeGuide } = useConceptGuideContext();
  const { isOpen, subtopicId, subtopicName, masteryScore } = state;

  // Close on Escape key
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
      {/* Backdrop — only rendered when open */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/10"
          onClick={closeGuide}
          aria-hidden="true"
        />
      )}

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`AI concept guide for ${subtopicName ?? "subtopic"}`}
        className={`fixed top-0 right-0 h-full w-[360px] z-50 bg-white border-l border-brand-border shadow-lg flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Drawer header */}
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

        {/* Scrollable content area */}
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
```

---

## Task 3 — Adapt ConceptGuidePanel to work inside the drawer

**File:** `src/components/my-progress/ConceptGuidePanel.tsx`

The existing component is a self-contained panel with its own header and close button. Extract the inner content into a named export `ConceptGuidePanelContent` that the drawer can render. The outer wrapper (`ConceptGuidePanel`) can remain for backward compatibility but will no longer be used after this task — do not delete it in this PR.

Add `masteryScore: number | null` to the props — pass it through to the API call context (the backend already uses it from the student profile, but having it in the request gives the LLM better context for the current session).

```tsx
// New export — the content without the wrapper card
export function ConceptGuidePanelContent({
  subtopicId,
  subtopicName,
  masteryScore,  // new prop — currently unused in API call, reserved for future
  onClose,
}: {
  subtopicId: string;
  subtopicName: string;
  masteryScore: number | null;
  onClose: () => void;
}) {
  // Move all the existing state and logic from ConceptGuidePanel here.
  // Remove the outer wrapper div (border, bg-brand-light, aria region).
  // The drawer provides that wrapper.
  // Add padding inside: className="p-4 space-y-4"
  // Keep all existing logic: question input, generate button, explanation, MCQ, reset.
  // The only visual change is removing the wrapper card styles.
}
```

Specifically:
1. Copy all state, hooks, and handler functions from `ConceptGuidePanel` into `ConceptGuidePanelContent`
2. Remove the outer `<div className="mt-2 rounded-xl border border-brand-primary/20 bg-brand-light p-4">` wrapper
3. Add a `<div className="p-4 space-y-4">` wrapper instead
4. Keep the close button removed from the content (the drawer header has its own close button)
5. Keep `ConceptGuidePanel` as-is for now — it will be removed in a separate cleanup PR

---

## Task 4 — Update SubtopicScoreRow to trigger the drawer

**File:** `src/components/my-progress/SubtopicScoreRow.tsx`

Replace the inline `showGuide` state and `ConceptGuidePanel` render with a context-driven trigger.

```tsx
import { useConceptGuideContext } from "../../context/ConceptGuideContext";

export function SubtopicScoreRow({ subtopicId, subtopicName, masteryScore, lastAssessedAt }: SubtopicScoreRowProps) {
  const { openGuide } = useConceptGuideContext();
  const { dotClass, textClass } = getMasteryStyle(masteryScore);
  const displayPct = scoreToPercent(masteryScore);

  const showExplainButton = masteryScore === null || masteryScore < 0.7;

  // Remove: const [showGuide, setShowGuide] = useState(false);

  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-brand-surface transition-colors">
      <div className="flex items-center gap-3">
        <div className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
        <span className="font-sans text-sm text-brand-ink">{subtopicName}</span>
      </div>
      <div className="flex items-center gap-4">
        {showExplainButton && (
          <button
            type="button"
            onClick={() => openGuide({ subtopicId, subtopicName, masteryScore })}
            className="font-sans text-xs text-brand-primary hover:text-brand-dark underline focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-1"
          >
            Explain this →
          </button>
        )}
        <span className={`font-sans text-sm font-semibold ${textClass}`}>{displayPct}</span>
        <span className="font-sans text-xs text-brand-muted w-36 text-right">
          {formatDate(lastAssessedAt)}
        </span>
      </div>
    </div>
    // Remove the old ConceptGuidePanel render that was below this div
  );
}
```

---

## Task 5 — Wrap MyProgress page with provider and render drawer

**File:** `src/pages/my-progress/MyProgress.tsx`

Import and add:

```tsx
import { ConceptGuideProvider } from "../../context/ConceptGuideContext";
import { ConceptGuideDrawer } from "../../components/ai/ConceptGuideDrawer";
```

Wrap the `StudentLayout` return in `ConceptGuideProvider` and add the drawer as a sibling to `StudentLayout`:

```tsx
return (
  <ConceptGuideProvider>
    <StudentLayout ...>
      {/* existing page content unchanged */}
    </StudentLayout>
    <ConceptGuideDrawer />
  </ConceptGuideProvider>
);
```

The `ConceptGuideDrawer` renders outside `StudentLayout` so it can overlay the full viewport including the sidebar.

---

## Acceptance Criteria

- [ ] Clicking "Explain this →" on a subtopic row (mastery < 70%) opens the right-side drawer
- [ ] Drawer slides in from the right with a CSS transition
- [ ] Drawer shows subtopic name in its header
- [ ] A backdrop scrim renders behind the drawer; clicking it closes the drawer
- [ ] Pressing Escape closes the drawer
- [ ] The X button in the drawer header closes the drawer
- [ ] Explanation generates correctly (same behavior as existing ConceptGuidePanel)
- [ ] MCQ check question renders and can be submitted
- [ ] "Ask a different question" reset works correctly
- [ ] Subtopics with mastery ≥ 70% do NOT show "Explain this →"
- [ ] Drawer does not push page content — it overlays
- [ ] TypeScript compiles with zero errors (`pnpm typecheck`)
- [ ] No ESLint errors (`pnpm lint`)
