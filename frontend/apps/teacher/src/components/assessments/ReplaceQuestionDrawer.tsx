import { useState } from "react";
import { Modal, Button, Skeleton, Badge } from "@kaihle/ui";
import { AlertTriangle } from "lucide-react";
import {
  useReplacementCandidates,
  useReplaceQuestion,
} from "../../hooks/useAssessmentQuestions";
import type { PreviewQuestion } from "../../hooks/useAssessmentPreview";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessmentId: string;
  question: PreviewQuestion | null;
  hasResponses: boolean;
  onSuccess?: () => void;
}

export function ReplaceQuestionDrawer({
  open,
  onOpenChange,
  assessmentId,
  question,
  hasResponses,
  onSuccess,
}: Props) {
  const [difficultyFilter, setDifficultyFilter] = useState<number | undefined>(
    undefined,
  );
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: candidates = [], isLoading } = useReplacementCandidates(
    assessmentId,
    open && question ? question.question_id : null,
    {
      difficulty_level: difficultyFilter,
      question_type: typeFilter,
    },
  );

  const replaceMutation = useReplaceQuestion(assessmentId);

  async function handleReplace() {
    if (!selectedId || !question) return;
    setErrorMsg(null);
    try {
      const result = await replaceMutation.mutateAsync({
        questionId: question.question_id,
        replacementQuestionId: selectedId,
      });
      if (result.has_responses_for_old) {
        // Show warning but still close — replacement already done
      }
      onSuccess?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to replace question.";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }

  if (!question) return null;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Replace Question"
      description="Choose a replacement from the same topic."
    >
      <div className="space-y-4">
        {/* Warning if responses exist */}
        {hasResponses && (
          <div className="flex items-start gap-3 bg-[#fffbeb] border border-[#fde68a] rounded-xl p-3">
            <AlertTriangle
              className="w-4 h-4 text-brand-gold-dark flex-shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <p className="text-xs font-sans text-brand-gold-dark leading-relaxed">
              Students have already answered this question. Replacing it will
              make their responses invisible in the detail view (scores are
              preserved).
            </p>
          </div>
        )}

        {/* Being replaced */}
        <div className="bg-brand-border-soft border border-brand-border rounded-xl p-3">
          <p className="text-[10px] font-sans font-bold uppercase tracking-widest text-brand-muted mb-1">
            Replacing
          </p>
          <p className="text-xs font-sans text-brand-body truncate">
            {question.question_text}
          </p>
        </div>

        {/* Filters */}
        <div className="flex gap-2 flex-wrap">
          <select
            value={difficultyFilter ?? ""}
            onChange={(e) =>
              setDifficultyFilter(
                e.target.value ? parseInt(e.target.value, 10) : undefined,
              )
            }
            className="border border-brand-border rounded-lg px-2 py-1.5 text-xs font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          >
            <option value="">Any difficulty</option>
            {[1, 2, 3, 4, 5].map((d) => (
              <option key={d} value={d}>
                Level {d}
              </option>
            ))}
          </select>
          <select
            value={typeFilter ?? ""}
            onChange={(e) => setTypeFilter(e.target.value || undefined)}
            className="border border-brand-border rounded-lg px-2 py-1.5 text-xs font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          >
            <option value="">Any type</option>
            <option value="MCQ">MCQ</option>
            <option value="TRUE_FALSE">True / False</option>
          </select>
        </div>

        {/* Candidates list */}
        <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
          {isLoading &&
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full rounded-xl" />
            ))}

          {!isLoading && candidates.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm font-sans text-brand-muted">
                No candidates found for this topic with the current filters.
              </p>
            </div>
          )}

          {candidates.map((c) => {
            const isSelected = selectedId === c.question_id;
            return (
              <button
                key={c.question_id}
                type="button"
                onClick={() => setSelectedId(c.question_id)}
                className={[
                  "w-full text-left p-3 rounded-xl border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold",
                  isSelected
                    ? "border-brand-gold bg-brand-gold-light"
                    : "border-brand-border bg-white hover:border-brand-gold-mid hover:bg-brand-light",
                ].join(" ")}
              >
                <p className="text-sm font-sans text-brand-ink leading-snug">
                  {c.question_text}
                </p>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <Badge variant="neutral">
                    {"⭐".repeat(Math.min(c.difficulty_level, 5))} Lvl{" "}
                    {c.difficulty_level}
                  </Badge>
                  <Badge variant="info">{c.subtopic_name}</Badge>
                  <Badge variant="neutral">{c.question_type}</Badge>
                </div>
              </button>
            );
          })}
        </div>

        {errorMsg && (
          <div className="bg-brand-red-light border border-brand-red/30 rounded-xl p-3">
            <p className="text-xs font-sans text-brand-red">{errorMsg}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            className="bg-brand-gold hover:bg-brand-gold-dark"
            onClick={() => void handleReplace()}
            disabled={!selectedId || replaceMutation.isPending}
          >
            {replaceMutation.isPending ? "Replacing…" : "Replace Question"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
