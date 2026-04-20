import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

interface ConceptGuideState {
  isOpen: boolean;
  subtopicId: string | null;
  subtopicName: string | null;
  masteryScore: number | null;
}

interface ConceptGuideContextValue {
  state: ConceptGuideState;
  openGuide: (params: {
    subtopicId: string;
    subtopicName: string;
    masteryScore: number | null;
  }) => void;
  closeGuide: () => void;
}

const ConceptGuideContext = createContext<ConceptGuideContextValue | null>(
  null,
);

const CLOSED_STATE: ConceptGuideState = {
  isOpen: false,
  subtopicId: null,
  subtopicName: null,
  masteryScore: null,
};

export function ConceptGuideProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConceptGuideState>(CLOSED_STATE);

  const openGuide = useCallback(
    (params: {
      subtopicId: string;
      subtopicName: string;
      masteryScore: number | null;
    }) => {
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
    throw new Error(
      "useConceptGuideContext must be used within ConceptGuideProvider",
    );
  }
  return ctx;
}
