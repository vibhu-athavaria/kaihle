/**
 * AddTopicModal - 2-step wizard for adding a topic to curriculum.
 *
 * Step 1: Choose to reuse existing topic OR create new topic
 * Step 2: Placement fields (standard_code, sequence_order, etc.)
 */

import { useState, useMemo } from "react";
import { Modal } from "@kaihle/ui";
import { Loader2, ChevronLeft, Search } from "lucide-react";
import { useGrades } from "../../hooks/useCurriculum";

type Step = "choose" | "placement";
type TopicChoice = "existing" | "new";

interface Topic {
  id: string;
  name: string;
  canonical_code: string | null;
}

interface AddTopicModalProps {
  curriculumId: string | null;
  subjectId: string | null;
  availableTopics: Topic[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    curriculumId: string;
    gradeId: string;
    subjectId: string;
    topicId?: string;
    topicData?: {
      name: string;
      canonical_code?: string;
      description?: string;
      keywords?: string[];
    };
    standardCode?: string;
    sequenceOrder?: number;
    learningObjectives: string[];
    recommendedWeeks?: number;
    isRequired: boolean;
  }) => Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export function AddTopicModal({
  curriculumId,
  subjectId,
  availableTopics,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  error,
}: AddTopicModalProps) {
  const { data: grades = [] } = useGrades();
  const [step, setStep] = useState<Step>("choose");
  const [choice, setChoice] = useState<TopicChoice | null>(null);
  const [selectedGradeId, setSelectedGradeId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  // Step 1: Existing topic selection
  const [selectedTopicId, setSelectedTopicId] = useState<string>("");

  // Step 1: New topic fields
  const [newTopicName, setNewTopicName] = useState("");
  const [newTopicCode, setNewTopicCode] = useState("");
  const [newTopicDescription, setNewTopicDescription] = useState("");
  const [newTopicKeywords, setNewTopicKeywords] = useState("");

  // Step 2: Placement fields
  const [standardCode, setStandardCode] = useState("");
  const [sequenceOrder, setSequenceOrder] = useState<string>("");
  const [learningObjectives, setLearningObjectives] = useState<string>("");
  const [recommendedWeeks, setRecommendedWeeks] = useState<string>("");
  const [isRequired, setIsRequired] = useState(true);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const resetForm = () => {
    setStep("choose");
    setChoice(null);
    setSelectedGradeId("");
    setSearchQuery("");
    setSelectedTopicId("");
    setNewTopicName("");
    setNewTopicCode("");
    setNewTopicDescription("");
    setNewTopicKeywords("");
    setStandardCode("");
    setSequenceOrder("");
    setLearningObjectives("");
    setRecommendedWeeks("");
    setIsRequired(true);
    setFieldErrors({});
  };

  const handleClose = () => {
    if (!isSubmitting) {
      resetForm();
      onClose();
    }
  };

  // Filter topics by search query
  const filteredTopics = useMemo(() => {
    if (!searchQuery.trim()) return availableTopics;
    const query = searchQuery.toLowerCase();
    return availableTopics.filter(
      (t) =>
        t.name.toLowerCase().includes(query) ||
        (t.canonical_code?.toLowerCase() || "").includes(query),
    );
  }, [availableTopics, searchQuery]);

  const validateStep1 = (): boolean => {
    const errors: Record<string, string> = {};

    if (!selectedGradeId) {
      errors.grade = "Please select a grade";
    }

    if (!choice) {
      errors.choice = "Please select an option";
    } else if (choice === "existing" && !selectedTopicId) {
      errors.topic = "Please select a topic";
    } else if (choice === "new") {
      if (!newTopicName.trim()) {
        errors.name = "Topic name is required";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const validateStep2 = (): boolean => {
    const errors: Record<string, string> = {};

    if (
      sequenceOrder &&
      (isNaN(parseInt(sequenceOrder, 10)) || parseInt(sequenceOrder, 10) < 1)
    ) {
      errors.sequenceOrder = "Sequence order must be a positive number";
    }

    if (
      recommendedWeeks &&
      (isNaN(parseInt(recommendedWeeks, 10)) ||
        parseInt(recommendedWeeks, 10) < 1)
    ) {
      errors.recommendedWeeks = "Recommended weeks must be a positive number";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleNext = () => {
    if (validateStep1()) {
      setStep("placement");
      setFieldErrors({});
    }
  };

  const handleBack = () => {
    setStep("choose");
    setFieldErrors({});
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      !curriculumId ||
      !selectedGradeId ||
      !subjectId ||
      !validateStep2() ||
      isSubmitting
    )
      return;

    const data: Parameters<typeof onSubmit>[0] = {
      curriculumId,
      gradeId: selectedGradeId,
      subjectId,
      learningObjectives: learningObjectives
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      isRequired,
    };

    if (choice === "existing") {
      data.topicId = selectedTopicId;
    } else {
      data.topicData = {
        name: newTopicName.trim(),
        canonical_code: newTopicCode.trim() || undefined,
        description: newTopicDescription.trim() || undefined,
        keywords: newTopicKeywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
      };
    }

    if (standardCode.trim()) data.standardCode = standardCode.trim();
    if (sequenceOrder) data.sequenceOrder = parseInt(sequenceOrder, 10);
    if (recommendedWeeks)
      data.recommendedWeeks = parseInt(recommendedWeeks, 10);

    await onSubmit(data);
    resetForm();
  };

  // Auto-generate code from name for new topic
  const handleNewTopicNameBlur = () => {
    if (!newTopicCode && newTopicName) {
      const autoCode = newTopicName
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .substring(0, 50);
      setNewTopicCode(autoCode);
    }
  };

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleClose}
      title={step === "choose" ? "Add topic" : "Topic placement"}
      description={
        step === "choose"
          ? "Choose whether to reuse an existing topic or create a new one."
          : "Configure how this topic appears in the curriculum."
      }
      maxWidth="lg"
    >
      {/* Step indicator */}
      <div className="flex items-center gap-2 mt-4 mb-6">
        <div
          className={`h-2 flex-1 rounded-full ${step === "choose" ? "bg-brand-primary" : "bg-brand-primary/30"}`}
        />
        <div
          className={`h-2 flex-1 rounded-full ${step === "placement" ? "bg-brand-primary" : "bg-gray-200"}`}
        />
      </div>

      <form
        onSubmit={
          step === "placement"
            ? handleSubmit
            : (e) => {
                e.preventDefault();
                handleNext();
              }
        }
      >
        {step === "choose" ? (
          <div className="space-y-4">
            {/* Grade selector */}
            <div>
              <label
                htmlFor="add-topic-grade"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Grade <span className="text-red-500">*</span>
              </label>
              <select
                id="add-topic-grade"
                value={selectedGradeId}
                onChange={(e) => setSelectedGradeId(e.target.value)}
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              >
                <option value="">Select a grade...</option>
                {grades.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
              {fieldErrors.grade && (
                <p className="mt-1 text-xs text-red-500">{fieldErrors.grade}</p>
              )}
            </div>

            {/* Choice buttons */}
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => {
                  setChoice("existing");
                  setFieldErrors({});
                }}
                className={`p-4 border-2 rounded-xl text-left transition-all ${
                  choice === "existing"
                    ? "border-brand-primary bg-brand-primary/5"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="font-medium text-gray-900">
                  Use existing topic
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  Link a topic that already exists in the system
                </div>
              </button>
              <button
                type="button"
                onClick={() => {
                  setChoice("new");
                  setFieldErrors({});
                }}
                className={`p-4 border-2 rounded-xl text-left transition-all ${
                  choice === "new"
                    ? "border-brand-primary bg-brand-primary/5"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="font-medium text-gray-900">
                  Create new topic
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  Create a brand new topic for this curriculum
                </div>
              </button>
            </div>
            {fieldErrors.choice && (
              <p className="text-xs text-red-500">{fieldErrors.choice}</p>
            )}

            {/* Existing topic selection */}
            {choice === "existing" && (
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700">
                  Select topic <span className="text-red-500">*</span>
                </label>
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search topics..."
                    className="w-full bg-white border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                  />
                </div>
                {/* Topic list */}
                <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg divide-y divide-gray-100">
                  {filteredTopics.length === 0 ? (
                    <div className="p-4 text-center text-gray-500 text-sm">
                      No topics found
                    </div>
                  ) : (
                    filteredTopics.map((topic) => (
                      <button
                        key={topic.id}
                        type="button"
                        onClick={() => setSelectedTopicId(topic.id)}
                        className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors flex items-center justify-between ${
                          selectedTopicId === topic.id
                            ? "bg-brand-primary/5"
                            : ""
                        }`}
                      >
                        <div>
                          <div className="font-medium text-gray-900">
                            {topic.name}
                          </div>
                          {topic.canonical_code && (
                            <div className="text-xs text-gray-500">
                              {topic.canonical_code}
                            </div>
                          )}
                        </div>
                        {selectedTopicId === topic.id && (
                          <div className="w-5 h-5 rounded-full bg-brand-primary text-white flex items-center justify-center text-xs">
                            ✓
                          </div>
                        )}
                      </button>
                    ))
                  )}
                </div>
                {fieldErrors.topic && (
                  <p className="text-xs text-red-500">{fieldErrors.topic}</p>
                )}
              </div>
            )}

            {/* New topic form */}
            {choice === "new" && (
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="new-topic-name"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Topic name <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="new-topic-name"
                    type="text"
                    value={newTopicName}
                    onChange={(e) => setNewTopicName(e.target.value)}
                    onBlur={handleNewTopicNameBlur}
                    placeholder="e.g., Linear Equations"
                    className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                  />
                  {fieldErrors.name && (
                    <p className="mt-1 text-xs text-red-500">
                      {fieldErrors.name}
                    </p>
                  )}
                </div>
                <div>
                  <label
                    htmlFor="new-topic-code"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Canonical code
                  </label>
                  <input
                    id="new-topic-code"
                    type="text"
                    value={newTopicCode}
                    onChange={(e) =>
                      setNewTopicCode(e.target.value.toUpperCase())
                    }
                    placeholder="e.g., MATH-ALG-LIN"
                    className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                  />
                </div>
                <div>
                  <label
                    htmlFor="new-topic-description"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Description
                  </label>
                  <textarea
                    id="new-topic-description"
                    value={newTopicDescription}
                    onChange={(e) => setNewTopicDescription(e.target.value)}
                    rows={2}
                    placeholder="Optional description"
                    className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
                  />
                </div>
                <div>
                  <label
                    htmlFor="new-topic-keywords"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Keywords
                  </label>
                  <input
                    id="new-topic-keywords"
                    type="text"
                    value={newTopicKeywords}
                    onChange={(e) => setNewTopicKeywords(e.target.value)}
                    placeholder="e.g., algebra, equations, linear (comma-separated)"
                    className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                  />
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Step 2: Placement */
          <div className="space-y-4">
            {/* Standard Code */}
            <div>
              <label
                htmlFor="standard-code"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Standard code
              </label>
              <input
                id="standard-code"
                type="text"
                value={standardCode}
                onChange={(e) => setStandardCode(e.target.value)}
                placeholder="e.g., 7Ma1, 8.NS.1"
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isSubmitting}
              />
              <p className="mt-1 text-xs text-gray-500">
                Official curriculum code (e.g., 7Ma1 for Grade 7 Math topic 1)
              </p>
            </div>

            {/* Sequence Order */}
            <div>
              <label
                htmlFor="sequence-order"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Sequence order
              </label>
              <input
                id="sequence-order"
                type="number"
                min={1}
                value={sequenceOrder}
                onChange={(e) => setSequenceOrder(e.target.value)}
                placeholder="Auto-assigned if blank"
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isSubmitting}
              />
              <p className="mt-1 text-xs text-gray-500">
                Teaching order within this subject/grade (1 = first)
              </p>
              {fieldErrors.sequenceOrder && (
                <p className="mt-1 text-xs text-red-500">
                  {fieldErrors.sequenceOrder}
                </p>
              )}
            </div>

            {/* Learning Objectives */}
            <div>
              <label
                htmlFor="learning-objectives"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Learning objectives
              </label>
              <textarea
                id="learning-objectives"
                value={learningObjectives}
                onChange={(e) => setLearningObjectives(e.target.value)}
                rows={3}
                placeholder="Enter one objective per line&#10;e.g., Solve linear equations with one variable"
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none resize-none"
                disabled={isSubmitting}
              />
              <p className="mt-1 text-xs text-gray-500">
                One objective per line
              </p>
            </div>

            {/* Recommended Weeks */}
            <div>
              <label
                htmlFor="recommended-weeks"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Recommended weeks
              </label>
              <input
                id="recommended-weeks"
                type="number"
                min={1}
                value={recommendedWeeks}
                onChange={(e) => setRecommendedWeeks(e.target.value)}
                placeholder="e.g., 2"
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isSubmitting}
              />
              {fieldErrors.recommendedWeeks && (
                <p className="mt-1 text-xs text-red-500">
                  {fieldErrors.recommendedWeeks}
                </p>
              )}
            </div>

            {/* Is Required Toggle */}
            <div className="flex items-center gap-3">
              <input
                id="is-required"
                type="checkbox"
                checked={isRequired}
                onChange={(e) => setIsRequired(e.target.checked)}
                className="w-4 h-4 text-brand-primary border-gray-300 rounded focus:ring-brand-primary"
                disabled={isSubmitting}
              />
              <label
                htmlFor="is-required"
                className="text-sm font-medium text-gray-700"
              >
                Required topic
              </label>
            </div>
            <p className="text-xs text-gray-500 -mt-3 ml-7">
              Required topics are part of the core curriculum.
            </p>
          </div>
        )}

        {/* Error from API */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg mt-4">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 justify-end pt-4 border-t border-gray-100 mt-6">
          {step === "placement" ? (
            <button
              type="button"
              onClick={handleBack}
              disabled={isSubmitting}
              className="px-4 py-2 border border-gray-200 text-gray-700 rounded-full text-sm font-medium font-['Inter'] hover:bg-gray-50 transition-colors disabled:opacity-50 flex items-center gap-1"
            >
              <ChevronLeft className="w-4 h-4" />
              Back
            </button>
          ) : (
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 border border-gray-200 text-gray-700 rounded-full text-sm font-medium font-['Inter'] hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-4 py-2 bg-brand-primary text-white rounded-full text-sm font-medium font-['Inter'] hover:bg-brand-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {step === "choose" ? "Next..." : "Adding..."}
              </>
            ) : step === "choose" ? (
              "Next"
            ) : (
              "Add topic"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
