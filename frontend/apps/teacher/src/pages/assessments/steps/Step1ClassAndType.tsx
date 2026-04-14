import { useAuth } from "@kaihle/auth";
import { ClipboardList, BookOpen, TrendingUp, Award } from "lucide-react";
import { Button } from "@kaihle/ui";
import {
  useAssessmentWizard,
  type AssessmentType,
} from "../../../hooks/useAssessmentWizard";
import { useTeacherClasses } from "../../../hooks/useTeacherClasses";

interface AssessmentTypeCard {
  type: AssessmentType;
  icon: React.ReactNode;
  title: string;
  description: string;
}

const ASSESSMENT_TYPES: AssessmentTypeCard[] = [
  {
    type: "DIAGNOSTIC",
    icon: <ClipboardList className="w-5 h-5" aria-hidden="true" />,
    title: "Diagnostic",
    description: "Assess baseline knowledge across all topics",
  },
  {
    type: "TOPIC_SPECIFIC",
    icon: <BookOpen className="w-5 h-5" aria-hidden="true" />,
    title: "Topic Specific",
    description: "Focus on selected topics for targeted assessment",
  },
  {
    type: "PROGRESS_CHECK",
    icon: <TrendingUp className="w-5 h-5" aria-hidden="true" />,
    title: "Progress Check",
    description: "Track student progress on chosen topics",
  },
  {
    type: "FINAL",
    icon: <Award className="w-5 h-5" aria-hidden="true" />,
    title: "Final",
    description: "End-of-term comprehensive assessment",
  },
];

export function Step1ClassAndType() {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? "";

  const { classId, assessmentType, setClassId, setAssessmentType, setStep } =
    useAssessmentWizard();

  const { data: classes = [], isLoading: classesLoading } = useTeacherClasses(
    schoolId || null,
    false,
  );

  const selectedClass = classes.find((c) => c.id === classId);

  const canProceed = !!classId && !!assessmentType;

  function handleNext() {
    if (!canProceed) return;
    const skipsTopics =
      assessmentType === "DIAGNOSTIC" || assessmentType === "FINAL";
    setStep(skipsTopics ? 3 : 2);
  }

  return (
    <div className="space-y-8">
      {/* Class selector */}
      <div>
        <label
          htmlFor="class-select"
          className="block text-sm font-sans font-semibold text-brand-ink mb-2"
        >
          Select Class
        </label>
        {classesLoading ? (
          <div className="h-10 bg-brand-border rounded-lg animate-pulse" />
        ) : (
          <select
            id="class-select"
            value={classId ?? ""}
            onChange={(e) => {
              const selected = classes.find((c) => c.id === e.target.value);
              if (selected)
                setClassId(
                  selected.id,
                  selected.name,
                  selected.subjectId,
                  selected.gradeId,
                  selected.curriculumId,
                );
            }}
            className="w-full max-w-sm border border-brand-border rounded-lg px-3 py-2.5 text-sm font-sans text-brand-ink bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1"
          >
            <option value="">Choose a class…</option>
            {classes.map((cls) => (
              <option key={cls.id} value={cls.id}>
                {cls.name}
              </option>
            ))}
          </select>
        )}
        {selectedClass && (
          <p className="mt-1 text-xs font-sans text-brand-muted">
            Selected: {selectedClass.name}
          </p>
        )}
      </div>

      {/* Assessment type cards */}
      <div>
        <p className="text-sm font-sans font-semibold text-brand-ink mb-3">
          Assessment Type
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {ASSESSMENT_TYPES.map((card) => {
            const isSelected = assessmentType === card.type;
            return (
              <button
                key={card.type}
                type="button"
                onClick={() => setAssessmentType(card.type)}
                className={[
                  "flex items-start gap-3 p-4 rounded-xl border text-left transition-all",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1",
                  isSelected
                    ? "border-brand-gold bg-brand-gold-light"
                    : "border-brand-border bg-white hover:border-brand-gold-mid hover:bg-brand-gold-light/30",
                ].join(" ")}
                aria-pressed={isSelected}
              >
                <span
                  className={[
                    "flex-shrink-0 mt-0.5",
                    isSelected ? "text-brand-gold-dark" : "text-brand-muted",
                  ].join(" ")}
                >
                  {card.icon}
                </span>
                <div>
                  <p
                    className={[
                      "text-sm font-sans font-bold",
                      isSelected ? "text-brand-gold-dark" : "text-brand-ink",
                    ].join(" ")}
                  >
                    {card.title}
                  </p>
                  <p className="text-xs font-sans text-brand-body mt-0.5 leading-relaxed">
                    {card.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
        {(assessmentType === "DIAGNOSTIC" || assessmentType === "FINAL") && (
          <p className="mt-2 text-xs font-sans text-brand-muted italic">
            Topic selection is not required for this assessment type.
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="flex justify-end pt-2">
        <Button
          variant="primary"
          className="bg-brand-gold hover:bg-brand-gold-dark"
          disabled={!canProceed}
          onClick={handleNext}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
