import { useState } from "react";
import { CheckCircle, XCircle, Edit3, Eye } from "lucide-react";
import type { ExplanationSection } from "../../hooks/useSubtopicContent";

interface ExplanationReviewPanelProps {
  explanation: ExplanationSection;
  onSave: (text: string, status: "approved" | "rejected") => void;
  isSaving?: boolean;
}

export function ExplanationReviewPanel({
  explanation,
  onSave,
  isSaving = false,
}: ExplanationReviewPanelProps) {
  const [editText, setEditText] = useState(explanation.explanation_text ?? "");
  const [preview, setPreview] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const isApproved = explanation.review_status === "approved";
  const isRejected = explanation.review_status === "rejected";

  const handleChange = (value: string) => {
    setEditText(value);
    setIsDirty(value !== (explanation.explanation_text ?? ""));
  };

  const charCount = editText.trim().length;
  const tooShort = charCount < 50;

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
              isApproved
                ? "bg-green-50 text-brand-primary border border-green-200"
                : isRejected
                  ? "bg-red-50 text-red-700 border border-red-200"
                  : "bg-amber-50 text-amber-700 border border-amber-200"
            }`}
          >
            {isApproved
              ? "Approved"
              : isRejected
                ? "Rejected"
                : "Pending review"}
          </span>
          {isDirty && (
            <span className="text-xs text-amber-600 font-medium">
              ● Unsaved changes
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setPreview((p) => !p)}
          className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand-primary transition-colors"
        >
          {preview ? (
            <>
              <Edit3 className="w-3.5 h-3.5" />
              Edit
            </>
          ) : (
            <>
              <Eye className="w-3.5 h-3.5" />
              Preview
            </>
          )}
        </button>
      </div>

      {/* Editor / Preview */}
      {preview ? (
        <div className="min-h-[160px] p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-800 whitespace-pre-wrap font-['Inter'] leading-relaxed">
          {editText || (
            <span className="text-gray-400 italic">
              Nothing to preview yet.
            </span>
          )}
        </div>
      ) : (
        <textarea
          value={editText}
          onChange={(e) => handleChange(e.target.value)}
          rows={8}
          disabled={isSaving}
          className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm font-['Inter'] leading-relaxed text-gray-800 focus:outline-none focus:ring-1 focus:ring-brand-primary resize-y disabled:opacity-50"
          placeholder="Explanation text (markdown supported)..."
        />
      )}

      <div className="flex items-center justify-between">
        <p
          className={`text-xs ${tooShort ? "text-amber-600" : "text-gray-400"}`}
        >
          {charCount} characters{tooShort ? " — minimum 50 required" : ""}
        </p>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isSaving || tooShort}
            onClick={() => onSave(editText, "rejected")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-red-200 text-red-600 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <XCircle className="w-3.5 h-3.5" />
            Reject
          </button>
          <button
            type="button"
            disabled={isSaving || tooShort}
            onClick={() => onSave(editText, "approved")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-primary text-white text-xs font-medium rounded-lg hover:bg-brand-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? (
              <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5" />
            )}
            {isSaving ? "Saving…" : isDirty ? "Save & Approve" : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}
