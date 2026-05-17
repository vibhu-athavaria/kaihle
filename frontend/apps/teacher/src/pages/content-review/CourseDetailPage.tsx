import { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import {
  useCourseDetail,
  useSetStudentOverride,
  useReviewVariant,
  type SubtopicVariant,
  type StudentCourseAssignment,
  type InterestCategoryMeta,
} from "../../hooks/useCourseDetail";
import { EmptyState, SkeletonCard, Modal } from "@kaihle/ui";
import {
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  Clock,
  UserCog,
  XCircle,
  Pencil,
} from "lucide-react";

// ── Variant pill ──────────────────────────────────────────────────────────────

function VariantStatusPill({ variant }: { variant: SubtopicVariant | null }) {
  if (!variant) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-50 text-brand-muted border border-brand-border">
        <Clock className="w-3 h-3" aria-hidden="true" />
        Not generated
      </span>
    );
  }
  switch (variant.review_status) {
    case "approved":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-brand-green-light text-brand-green border border-brand-green/20">
          <CheckCircle className="w-3 h-3" aria-hidden="true" />
          Approved
        </span>
      );
    case "rejected":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-brand-red-light text-brand-red border border-brand-red/20">
          <AlertCircle className="w-3 h-3" aria-hidden="true" />
          Rejected
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-[#fffbeb] text-brand-gold border border-brand-gold/20">
          <Clock className="w-3 h-3" aria-hidden="true" />
          Pending
        </span>
      );
  }
}

// ── Preview / review / edit modal ────────────────────────────────────────────

function PreviewModal({
  variant,
  subtopicName,
  classId,
  topicId,
  open,
  onClose,
}: {
  variant: SubtopicVariant | null;
  subtopicName: string;
  classId: string;
  topicId: string;
  open: boolean;
  onClose: () => void;
}) {
  const reviewMutation = useReviewVariant(classId, topicId);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(variant?.explanation_text ?? "");
  const [rejectNote, setRejectNote] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  function handleApprove() {
    if (!variant) return;
    reviewMutation.mutate(
      { content_id: variant.content_id, review_status: "approved" },
      { onSuccess: onClose },
    );
  }

  function handleReject() {
    if (!variant) return;
    reviewMutation.mutate(
      {
        content_id: variant.content_id,
        review_status: "rejected",
        teacher_note: rejectNote,
      },
      {
        onSuccess: () => {
          setRejectNote("");
          setShowRejectInput(false);
          onClose();
        },
      },
    );
  }

  function handleSaveEdit() {
    if (!variant) return;
    // Approve with edited text via the same review endpoint — save edit first via PATCH
    reviewMutation.mutate(
      {
        content_id: variant.content_id,
        review_status: "approved",
        edited_text: editText,
      },
      {
        onSuccess: () => {
          setEditing(false);
          onClose();
        },
      },
    );
  }

  return (
    <Modal open={open} onOpenChange={onClose} title={subtopicName}>
      <div className="space-y-4">
        {variant ? (
          <>
            <div className="flex items-center gap-2">
              <VariantStatusPill variant={variant} />
              <span className="text-xs text-brand-muted">
                {variant.interest_label}
              </span>
              {!editing && (
                <button
                  type="button"
                  onClick={() => {
                    setEditText(variant.explanation_text);
                    setEditing(true);
                  }}
                  className="ml-auto inline-flex items-center gap-1 text-xs text-brand-muted hover:text-brand-ink transition-colors"
                  aria-label="Edit content"
                >
                  <Pencil className="w-3 h-3" aria-hidden="true" />
                  Edit
                </button>
              )}
            </div>

            {editing ? (
              <div className="space-y-2">
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  rows={10}
                  className="w-full rounded-lg border border-brand-border px-3 py-2 text-sm text-brand-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 resize-y"
                  aria-label="Edit explanation text"
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(false)}
                    className="px-3 py-1.5 text-sm font-medium text-brand-ink border border-brand-border rounded-full hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEdit}
                    disabled={reviewMutation.isPending}
                    className="px-3 py-1.5 text-sm font-medium text-white bg-brand-gold rounded-full hover:bg-brand-gold-dark disabled:opacity-60"
                  >
                    {reviewMutation.isPending ? "Saving…" : "Save & Approve"}
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-brand-body leading-relaxed whitespace-pre-wrap">
                {variant.explanation_text}
              </p>
            )}

            {!editing && variant.review_status !== "approved" && (
              <div className="space-y-2 pt-1 border-t border-brand-border">
                {showRejectInput ? (
                  <div className="space-y-2">
                    <textarea
                      value={rejectNote}
                      onChange={(e) => setRejectNote(e.target.value)}
                      rows={2}
                      placeholder="Reason for rejection (optional)"
                      className="w-full rounded-lg border border-brand-border px-3 py-2 text-sm text-brand-ink placeholder:text-brand-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 resize-none"
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => setShowRejectInput(false)}
                        className="px-3 py-1.5 text-sm text-brand-muted hover:text-brand-ink"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleReject}
                        disabled={reviewMutation.isPending}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-brand-red rounded-full hover:bg-brand-red/90 disabled:opacity-60"
                      >
                        <XCircle className="w-3.5 h-3.5" aria-hidden="true" />
                        {reviewMutation.isPending
                          ? "Rejecting…"
                          : "Confirm Reject"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleApprove}
                      disabled={reviewMutation.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-gold border border-brand-gold/30 rounded-full hover:bg-brand-gold/5 disabled:opacity-60 transition-colors"
                    >
                      <CheckCircle className="w-4 h-4" aria-hidden="true" />
                      {reviewMutation.isPending ? "Approving…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRejectInput(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-red border border-brand-red/30 rounded-full hover:bg-brand-red-light transition-colors"
                    >
                      <XCircle className="w-4 h-4" aria-hidden="true" />
                      Reject
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-brand-muted">
            No content generated for this variant yet.
          </p>
        )}
      </div>
    </Modal>
  );
}

// ── Student override modal ────────────────────────────────────────────────────

function OverrideModal({
  student,
  categories,
  classId,
  topicId,
  open,
  onClose,
}: {
  student: StudentCourseAssignment;
  categories: InterestCategoryMeta[];
  classId: string;
  topicId: string;
  open: boolean;
  onClose: () => void;
}) {
  const setOverride = useSetStudentOverride(classId, topicId);
  const [selected, setSelected] = useState<string | null>(
    student.override_interest_category ?? null,
  );

  function handleSave() {
    const catId = selected
      ? (categories.find((c) => c.name === selected)?.id ?? null)
      : null;
    setOverride.mutate(
      { student_id: student.student_id, interest_category_id: catId },
      { onSuccess: onClose },
    );
  }

  const interestLabel: Record<string, string> = {
    sports_movement: "Sports & Fitness",
    tech_gaming: "Technology & Innovation",
    nature_animals: "Nature & Science",
    arts_culture: "Music & Arts",
  };

  return (
    <Modal
      open={open}
      onOpenChange={onClose}
      title={`Assign variant — ${student.student_name}`}
    >
      <div className="space-y-4">
        <p className="text-sm text-brand-body">
          System auto-assigns{" "}
          <span className="font-semibold text-brand-ink">
            {student.auto_interest_category
              ? (interestLabel[student.auto_interest_category] ??
                student.auto_interest_category)
              : "no preference (no learning profile)"}
          </span>{" "}
          based on {student.student_name}&apos;s learning profile.
        </p>

        <div className="space-y-2">
          <p className="text-xs font-semibold text-brand-ink">Override to:</p>
          <button
            type="button"
            onClick={() => setSelected(null)}
            className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
              selected === null
                ? "border-brand-gold bg-[#fffbeb] text-brand-gold font-semibold"
                : "border-brand-border text-brand-body hover:border-brand-gold/50"
            }`}
          >
            Auto (no override)
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelected(cat.name)}
              className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 ${
                selected === cat.name
                  ? "border-brand-gold bg-[#fffbeb] text-brand-gold font-semibold"
                  : "border-brand-border text-brand-body hover:border-brand-gold/50"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-brand-ink border border-brand-border rounded-full hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={setOverride.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-brand-gold rounded-full hover:bg-brand-gold-dark disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
          >
            {setOverride.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function CourseDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const [searchParams] = useSearchParams();
  const classId = searchParams.get("classId") ?? "";

  const { data, isLoading, isError } = useCourseDetail(
    classId || null,
    topicId ?? null,
  );

  const [previewState, setPreviewState] = useState<{
    subtopicName: string;
    variant: SubtopicVariant | null;
  } | null>(null);

  const [overrideStudent, setOverrideStudent] =
    useState<StudentCourseAssignment | null>(null);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <EmptyState
          emoji="⚠️"
          title="Could not load course detail"
          description="Try refreshing the page."
        />
      </div>
    );
  }

  const interestLabel: Record<string, string> = {
    sports_movement: "Sports & Fitness",
    tech_gaming: "Technology & Innovation",
    nature_animals: "Nature & Science",
    arts_culture: "Music & Arts",
  };

  const categoryNames = data.interest_categories.map((c) => c.name);

  return (
    <div className="p-6 space-y-8">
      {/* Header */}
      <div>
        <Link
          to="/teacher/content-review"
          className="inline-flex items-center gap-1.5 text-sm text-brand-muted hover:text-brand-ink transition-colors mb-3"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Content Review
        </Link>
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          {data.topic_name}
        </h1>
        <p className="text-sm text-brand-muted mt-1">
          {data.subtopics.length} subtopic
          {data.subtopics.length !== 1 ? "s" : ""} · {data.students.length}{" "}
          student{data.students.length !== 1 ? "s" : ""} enrolled
        </p>
      </div>

      {/* 4-variant content grid */}
      <section>
        <h2 className="font-display font-semibold text-lg text-brand-ink mb-4">
          Content variants by subtopic
        </h2>
        <p className="text-sm text-brand-muted mb-4">
          Each subtopic has up to 4 interest-personalised versions. Click a cell
          to preview the content.
        </p>

        {data.subtopics.length === 0 ? (
          <EmptyState
            emoji="📝"
            title="No subtopics found"
            description="This topic has no active subtopics in the curriculum."
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-brand-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-brand-border">
                  <th className="text-left px-4 py-3 font-semibold text-brand-ink text-xs uppercase tracking-wide w-48">
                    Subtopic
                  </th>
                  {data.interest_categories.map((cat) => (
                    <th
                      key={cat.id}
                      className="text-center px-4 py-3 font-semibold text-brand-ink text-xs uppercase tracking-wide"
                    >
                      {cat.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.subtopics.map((subtopic, idx) => (
                  <tr
                    key={subtopic.subtopic_id}
                    className={idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}
                  >
                    <td className="px-4 py-3 font-medium text-brand-ink border-r border-brand-border">
                      {subtopic.subtopic_name}
                    </td>
                    {categoryNames.map((catName) => {
                      const variant = subtopic.variants[catName] ?? null;
                      return (
                        <td key={catName} className="px-4 py-3 text-center">
                          <button
                            type="button"
                            onClick={() =>
                              setPreviewState({
                                subtopicName: subtopic.subtopic_name,
                                variant,
                              })
                            }
                            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 rounded"
                            aria-label={`Preview ${interestLabel[catName] ?? catName} variant for ${subtopic.subtopic_name}`}
                          >
                            <VariantStatusPill variant={variant} />
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Student assignments */}
      <section>
        <h2 className="font-display font-semibold text-lg text-brand-ink mb-2">
          Student variant assignments
        </h2>
        <p className="text-sm text-brand-muted mb-4">
          The system auto-assigns each student the variant that best matches
          their learning interests. You can override it per student.
        </p>

        {data.students.length === 0 ? (
          <EmptyState
            emoji="👤"
            title="No students enrolled"
            description="Enrol students in this class to see their variant assignments."
          />
        ) : (
          <div className="space-y-2">
            {data.students.map((student) => (
              <div
                key={student.student_id}
                className="bg-white rounded-xl border border-brand-border px-4 py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <p className="font-medium text-brand-ink text-sm">
                    {student.student_name}
                  </p>
                  <p className="text-xs text-brand-muted">{student.email}</p>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {student.override_interest_category ? (
                    <div className="text-right">
                      <span className="text-xs font-semibold text-brand-gold px-2 py-0.5 bg-[#fffbeb] rounded-full border border-brand-gold/20">
                        {interestLabel[student.override_interest_category] ??
                          student.override_interest_category}
                      </span>
                      <p className="text-xs text-brand-muted mt-0.5">
                        Teacher override
                      </p>
                    </div>
                  ) : (
                    <div className="text-right">
                      <span className="text-xs font-medium text-brand-body px-2 py-0.5 bg-gray-50 rounded-full border border-brand-border">
                        {student.auto_interest_category
                          ? (interestLabel[student.auto_interest_category] ??
                            student.auto_interest_category)
                          : "No preference"}
                      </span>
                      <p className="text-xs text-brand-muted mt-0.5">
                        Auto-assigned
                      </p>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => setOverrideStudent(student)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-ink border border-brand-border rounded-full hover:border-brand-gold hover:text-brand-gold transition-colors focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
                    aria-label={`Override variant for ${student.student_name}`}
                  >
                    <UserCog className="w-3.5 h-3.5" aria-hidden="true" />
                    Override
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Preview modal */}
      {previewState && (
        <PreviewModal
          variant={previewState.variant}
          subtopicName={previewState.subtopicName}
          classId={classId}
          topicId={topicId!}
          open={!!previewState}
          onClose={() => setPreviewState(null)}
        />
      )}

      {/* Override modal */}
      {overrideStudent && (
        <OverrideModal
          student={overrideStudent}
          categories={data.interest_categories}
          classId={classId}
          topicId={topicId!}
          open={!!overrideStudent}
          onClose={() => setOverrideStudent(null)}
        />
      )}
    </div>
  );
}
