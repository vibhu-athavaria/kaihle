import { useParams, useNavigate } from "react-router-dom";
import {
  ChevronRight,
  ArrowRight,
  BookOpen,
  CheckCircle,
  PlayCircle,
} from "lucide-react";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useClassTopics } from "../../hooks/useClassTopics";
import { useTopicSubtopics } from "../../hooks/useTopicSubtopics";
import type { SubtopicStatus } from "../../hooks/useTopicSubtopics";

type CardStatus = SubtopicStatus | "no_content";

function deriveCardStatus(
  hasContent: boolean,
  progressStatus: SubtopicStatus | undefined,
): CardStatus {
  if (!hasContent) return "no_content";
  return progressStatus ?? "not_started";
}

function getCardCtaLabel(status: CardStatus): string {
  switch (status) {
    case "no_content":
      return "Coming soon";
    case "completed":
      return "Review";
    case "in_progress":
      return "Resume";
    default:
      return "Start";
  }
}

interface BadgeStyle {
  containerClass: string;
  label: string;
}

function getCardBadgeStyle(status: CardStatus): BadgeStyle {
  switch (status) {
    case "no_content":
      return {
        containerClass: "bg-brand-muted/20 text-brand-muted font-medium",
        label: "Coming soon",
      };
    case "completed":
      return {
        containerClass: "bg-brand-green-light text-brand-green font-semibold",
        label: "Finished",
      };
    case "in_progress":
      return {
        containerClass: "bg-brand-gold/10 text-brand-amber font-semibold",
        label: "In progress",
      };
    default:
      return {
        containerClass: "bg-brand-primary/10 text-brand-primary font-medium",
        label: "Not started",
      };
  }
}

export function TopicDetailPage() {
  const { classId, topicId } = useParams<{
    classId: string;
    topicId: string;
  }>();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();

  const { data: topics } = useClassTopics(classId!);
  const topicData = topics?.find((t) => t.id === topicId);

  const {
    data: subtopics,
    isPending,
    isError,
  } = useTopicSubtopics(classId!, topicId!);

  const classInfo = layout.sidebarClasses.find((c) => c.id === classId);

  return (
    <StudentLayout
      activeNav="home"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      onLogout={layout.onLogout}
      assessmentBadge={layout.assessmentBadge}
    >
      <div className="space-y-6">
        {/* Breadcrumb */}
        <nav
          className="flex items-center gap-1.5 font-sans text-sm text-brand-body flex-wrap"
          aria-label="Breadcrumb"
        >
          <button
            onClick={() => navigate("/student/dashboard")}
            className="hover:text-brand-ink transition-colors"
          >
            Dashboard
          </button>
          <ChevronRight className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          <button
            onClick={() => navigate(`/student/classes/${classId}`)}
            className="hover:text-brand-ink transition-colors truncate max-w-[120px]"
          >
            {classInfo?.name || classInfo?.subjectName || "Class"}
          </button>
          <ChevronRight className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          <span className="text-brand-ink font-medium truncate">
            {topicData?.name ?? "Topic"}
          </span>
        </nav>

        {/* Topic header card */}
        <div className="bg-white rounded-card border border-brand-border p-5 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
              <BookOpen
                className="w-6 h-6 text-brand-primary"
                aria-hidden="true"
              />
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="font-display font-bold text-2xl text-brand-ink">
                {topicData?.name ?? "Topic"}
              </h1>
              {subtopics && subtopics.length > 0 && (
                <span className="inline-block mt-1.5 px-2.5 py-0.5 bg-brand-primary/10 text-brand-primary text-xs font-semibold rounded-full">
                  {subtopics.length} subtopic{subtopics.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Subtopics grid */}
        {isError ? (
          <div className="text-center py-8">
            <p className="font-sans text-sm text-brand-body">
              Something went wrong loading subtopics. Please refresh the page.
            </p>
          </div>
        ) : isPending ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-28 bg-brand-border rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : subtopics && subtopics.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {subtopics.map((subtopic) => {
              const cardStatus = deriveCardStatus(
                subtopic.has_content,
                subtopic.progress?.status,
              );
              const badge = getCardBadgeStyle(cardStatus);
              const ctaLabel = getCardCtaLabel(cardStatus);
              const isDisabled = cardStatus === "no_content";

              return (
                <button
                  key={subtopic.id}
                  onClick={() => {
                    if (!isDisabled)
                      navigate(`/student/subtopics/${subtopic.id}/course`);
                  }}
                  disabled={isDisabled}
                  aria-disabled={isDisabled}
                  className={[
                    "group text-left bg-white rounded-xl border p-5 shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
                    isDisabled
                      ? "border-brand-border cursor-not-allowed opacity-70"
                      : "border-brand-border hover:border-brand-primary hover:shadow-md",
                  ].join(" ")}
                >
                  <div className="flex flex-col h-full gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-sans font-semibold text-base text-brand-ink leading-snug">
                        {subtopic.name}
                      </h3>
                      <span
                        className={`inline-block mt-2 px-2 py-0.5 text-xs rounded-full ${badge.containerClass}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                    <div
                      className={`flex items-center gap-1 text-xs font-semibold transition-all ${
                        isDisabled
                          ? "text-brand-muted"
                          : "text-brand-primary group-hover:gap-2"
                      }`}
                    >
                      {cardStatus === "completed" ? (
                        <CheckCircle
                          className="w-3.5 h-3.5"
                          aria-hidden="true"
                        />
                      ) : cardStatus === "in_progress" ? (
                        <PlayCircle
                          className="w-3.5 h-3.5"
                          aria-hidden="true"
                        />
                      ) : cardStatus === "no_content" ? null : (
                        <ArrowRight
                          className="w-3.5 h-3.5"
                          aria-hidden="true"
                        />
                      )}
                      {ctaLabel}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-16 px-6">
            <div className="text-4xl mb-4">📚</div>
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No subtopics yet
            </h3>
            <p className="font-sans text-brand-body text-sm max-w-sm mx-auto">
              Your teacher will add content soon.
            </p>
          </div>
        )}
      </div>
    </StudentLayout>
  );
}
