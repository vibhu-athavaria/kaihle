import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { StudentLayout } from "@kaihle/ui";
import { SubjectScoreCard } from "./SubjectScoreCard";
import { NextStepCard, EmptyNextSteps } from "./NextStepCard";
import { StreakBadge } from "./StreakBadge";
import { useStudentDashboard } from "../../hooks/useStudentDashboard";
function getGreeting() {
    const hour = new Date().getHours();
    if (hour < 12)
        return "Good morning";
    if (hour < 18)
        return "Good afternoon";
    return "Good evening";
}
function SkeletonCard() {
    return (_jsxs("div", { className: "bg-white rounded-2xl border border-brand-border p-4 text-center animate-pulse", children: [_jsx("div", { className: "h-8 w-16 bg-brand-border rounded mx-auto mb-2" }), _jsx("div", { className: "h-3 w-20 bg-brand-border-soft rounded mx-auto" }), _jsx("div", { className: "h-2 w-12 bg-brand-border-soft rounded mx-auto mt-1" })] }));
}
function SkeletonNextStep() {
    return (_jsx("div", { className: "bg-white rounded-2xl border border-brand-border p-4 animate-pulse", children: _jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: "w-8 h-8 bg-brand-border rounded-full" }), _jsxs("div", { className: "flex-1", children: [_jsx("div", { className: "h-4 w-32 bg-brand-border rounded mb-2" }), _jsx("div", { className: "h-3 w-24 bg-brand-border-soft rounded" })] })] }) }));
}
export function StudentDashboard() {
    const { data, isLoading, isError } = useStudentDashboard();
    if (isError) {
        return (_jsx(StudentLayout, { activeNav: "home", children: _jsx("div", { className: "text-center py-8", children: _jsx("p", { className: "text-brand-red", children: "Failed to load dashboard data." }) }) }));
    }
    const greeting = getGreeting();
    const firstName = data?.studentInfo.firstName || "";
    const gradeName = data?.studentInfo.gradeName || "";
    const curriculumName = data?.studentInfo.curriculumName || "";
    const subjects = data?.gapMap.subjects || [];
    const studyPlans = data?.studyPlans || [];
    const assessments = data?.assessments || [];
    const activeStudyPlans = studyPlans.filter((sp) => sp.status === "ACTIVE");
    const inProgressStudyPlans = studyPlans.filter((sp) => sp.status === "IN_PROGRESS");
    const weakestSubject = subjects.length > 0
        ? subjects.reduce((weakest, current) => current.score !== null &&
            (weakest.score === null || current.score < weakest.score)
            ? current
            : weakest, subjects[0])
        : null;
    const nextSteps = [];
    if (assessments.length > 0) {
        nextSteps.push({
            type: "assessment",
            title: `${assessments.length} assessment${assessments.length > 1 ? "s" : ""} due`,
            subtitle: `${assessments[0].subjectName} · Due ${new Date(assessments[0].dueDate).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
            })}`,
            actionLabel: "Start now →",
        });
    }
    if (activeStudyPlans.length > 0) {
        nextSteps.push({
            type: "study-plan-ready",
            title: `${activeStudyPlans.length} study plan${activeStudyPlans.length > 1 ? "s" : ""} ready`,
            subtitle: "Start learning where it counts",
            actionLabel: "View plans →",
        });
    }
    if (inProgressStudyPlans.length > 0) {
        nextSteps.push({
            type: "study-plan-progress",
            title: "Continue your study plan",
            subtitle: inProgressStudyPlans[0].title,
            actionLabel: "Continue →",
        });
    }
    if (weakestSubject &&
        weakestSubject.score !== null &&
        weakestSubject.score < 0.4) {
        nextSteps.push({
            type: "weakest-area",
            title: `Your weakest area: ${weakestSubject.subjectName}`,
            subtitle: `${Math.round(weakestSubject.score * 100)}%`,
            actionLabel: "See what to work on →",
        });
    }
    return (_jsx(StudentLayout, { activeNav: "home", children: _jsxs("div", { className: "space-y-6", children: [_jsxs("div", { children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsxs("h1", { className: "font-display font-bold text-2xl text-brand-ink", children: [greeting, firstName ? `, ${firstName}` : "", " \uD83D\uDC4B"] }), _jsx(StreakBadge, { days: 3 })] }), gradeName && curriculumName && (_jsxs("p", { className: "font-sans text-sm text-brand-muted mt-1", children: [gradeName, " \u00B7 ", curriculumName] }))] }), _jsx("div", { children: _jsx("div", { className: "grid grid-cols-3 gap-3", children: isLoading
                            ? Array.from({ length: 3 }).map((_, i) => _jsx(SkeletonCard, {}, i))
                            : subjects
                                .slice(0, 3)
                                .map((subject) => (_jsx(SubjectScoreCard, { subjectName: subject.subjectName, subjectCode: subject.subjectCode, score: subject.score }, subject.subjectCode))) }) }), nextSteps.length > 0 && (_jsxs("div", { children: [_jsx("h2", { className: "font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3", children: "What's waiting for you" }), _jsx("div", { className: "space-y-3", children: isLoading
                                ? Array.from({ length: 2 }).map((_, i) => _jsx(SkeletonNextStep, {}, i))
                                : nextSteps
                                    .slice(0, 3)
                                    .map((step, index) => (_jsx(NextStepCard, { type: step.type, title: step.title, subtitle: step.subtitle, actionLabel: step.actionLabel }, index))) })] })), nextSteps.length === 0 && !isLoading && (_jsxs("div", { children: [_jsx("h2", { className: "font-sans text-sm font-bold text-brand-muted uppercase tracking-wide mb-3", children: "Keep going" }), _jsx(EmptyNextSteps, {})] }))] }) }));
}
