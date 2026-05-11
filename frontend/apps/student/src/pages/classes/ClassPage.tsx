import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
import { TopicsTab } from "./tabs/TopicsTab";
import { StudyPlanTab } from "./tabs/StudyPlanTab";
import { MyProgressTab } from "./tabs/MyProgressTab";

type TabKey = "topics" | "study-plan" | "progress";

const TABS: { key: TabKey; label: string }[] = [
  { key: "topics", label: "Topics" },
  { key: "study-plan", label: "Study plan" },
  { key: "progress", label: "My progress" },
];

export function ClassPage() {
  const { classId } = useParams<{ classId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const layout = useStudentLayoutProps();

  // Use already-cached dashboard data to avoid an extra API call for class metadata
  const { data: dashboard, isLoading: isDashboardLoading } =
    useStudentDashboard();
  const classData = dashboard?.classes.find((c) => c.class_id === classId);

  const activeTab = (searchParams.get("tab") as TabKey | null) ?? "topics";

  function setTab(tab: TabKey) {
    if (tab === "topics") {
      setSearchParams({});
    } else {
      setSearchParams({ tab });
    }
  }

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
          className="flex items-center gap-1.5 font-sans text-sm text-brand-body"
          aria-label="Breadcrumb"
        >
          <button
            onClick={() => navigate("/student/dashboard")}
            className="hover:text-brand-ink transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
          >
            Dashboard
          </button>
          <ChevronRight className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          <span className="text-brand-ink font-medium truncate">
            {classData?.class_name ?? classData?.subject_name ?? "Class"}
          </span>
        </nav>

        {/* Class header card */}
        <div className="bg-white rounded-card border border-brand-border p-5 shadow-sm">
          {isDashboardLoading && !classData ? (
            <div className="flex items-start gap-4 animate-pulse">
              <div className="w-12 h-12 rounded-full bg-brand-border flex-shrink-0" />
              <div className="flex-1 min-w-0 space-y-2">
                <div className="h-7 bg-brand-border rounded-full w-48" />
                <div className="h-5 bg-brand-border rounded-full w-32" />
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
                <span
                  className="font-display font-bold text-lg text-brand-primary"
                  aria-hidden="true"
                >
                  {classData?.subject_name?.[0] ?? "?"}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <h1 className="font-display font-bold text-2xl text-brand-ink">
                  {classData?.class_name ?? classData?.subject_name ?? "Class"}
                </h1>
                <p className="font-sans text-sm text-brand-body mt-0.5">
                  {[classData?.teacher_name, classData?.subject_name]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Tab bar */}
        <div
          className="flex gap-0 border-b border-brand-border"
          role="tablist"
          aria-label="Class sections"
        >
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              role="tab"
              aria-selected={activeTab === key}
              aria-controls={`tabpanel-${key}`}
              onClick={() => setTab(key)}
              className={[
                "px-4 py-3 font-sans text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded-t",
                activeTab === key
                  ? "text-brand-primary border-b-2 border-brand-primary -mb-px"
                  : "text-brand-body hover:text-brand-ink",
              ].join(" ")}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div
          id={`tabpanel-${activeTab}`}
          role="tabpanel"
          aria-label={TABS.find((t) => t.key === activeTab)?.label}
        >
          {activeTab === "topics" && <TopicsTab classId={classId!} />}
          {activeTab === "study-plan" && (
            <StudyPlanTab
              classId={classId!}
              diagnosticStatus={classData?.diagnostic_status ?? "PENDING"}
            />
          )}
          {activeTab === "progress" && classData?.subject_id && (
            <MyProgressTab subjectId={classData.subject_id} />
          )}
          {activeTab === "progress" && !classData?.subject_id && (
            <div className="text-center py-16 px-6">
              <p className="font-sans text-sm text-brand-body">
                Loading class information…
              </p>
            </div>
          )}
        </div>
      </div>
    </StudentLayout>
  );
}
