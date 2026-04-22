# Student Assessments Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the student Assessments page actually show assessments, add a sidebar badge for new ones, fix multi-class assessment fetching on the dashboard, and eliminate duplicated hook calls across all student pages.

**Architecture:** Create a `useStudentAssessments(classIds, studentId)` hook that fans out parallel class-scoped assessment queries and one attempt-history query, merges results, separates diagnostics from teacher assessments, and computes a badge count. Enhance `useStudentLayoutProps` to include the badge count so every page gets it for free via the sidebar. Rebuild `Assessments.tsx` to use real data. Fix `useStudentDashboard` to cover all enrolled classes. Switch all pages to `useStudentLayoutProps` to eliminate the repeated `useStudentInfo + useMyClasses + manual mapping` pattern.

**Tech Stack:** React Query v5 (`useQueries`), React Testing Library (`renderHook`), Jest, TypeScript strict mode, Tailwind CSS tokens per DESIGN_SYSTEM.md §5.4.

**Branch:** `student/assessments-page-fix`

**⚠️ Scope note on teacher assessment Start button:** There is no backend endpoint to create a Tier 2 (teacher-created) attempt. Diagnostic attempts are pre-created at enrollment. Teacher assessment cards will show status and metadata only — no Start button — until a future backend task adds `POST /api/v1/assessments/{id}/start`. Diagnostics retain their existing Start/Continue/View Results flow via `diagnosticAttemptId`.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `frontend/apps/student/src/hooks/useStudentInfo.ts` | Add `id`, `enrolledClasses` to `StudentInfo` interface |
| Create | `frontend/apps/student/src/hooks/useStudentAssessments.ts` | Fan-out assessment + attempt queries; classify + badge |
| Create | `frontend/apps/student/src/hooks/__tests__/useStudentAssessments.test.ts` | Tests for the new hook |
| Modify | `frontend/packages/ui/src/layouts/StudentLayout.tsx` | Add `assessmentBadge?: number` prop, wire to Assessments nav item |
| Modify | `frontend/apps/student/src/hooks/useStudentLayoutProps.ts` | Call `useStudentAssessments`, return `assessmentBadgeCount` |
| Modify | `frontend/apps/student/src/hooks/__tests__/useStudentLayoutProps.test.ts` | Update tests for badge |
| Modify | `frontend/apps/student/src/pages/assessments/Assessments.tsx` | Rebuild: real data, Get Started section, teacher list |
| Modify | `frontend/apps/student/src/hooks/useStudentDashboard.ts` | Fix to use `enrolledClasses[]` instead of single `classId`; import `useStudentAssessments` |
| Modify | `frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx` | Switch to `useStudentLayoutProps` |
| Modify | `frontend/apps/student/src/pages/my-progress/MyProgress.tsx` | Switch to `useStudentLayoutProps` |
| Modify | `frontend/apps/student/src/pages/study-plans/StudyPlans.tsx` | Switch to `useStudentLayoutProps` |
| Modify | `frontend/apps/student/src/pages/settings/StudentSettings.tsx` | Switch to `useStudentLayoutProps` |
| Modify | `frontend/apps/student/src/pages/assessments/TakeAssessmentPage.tsx` | Switch to `useStudentLayoutProps` |

---

## Task 1: Add `id` and `enrolledClasses` to `useStudentInfo`

The backend already returns these fields. The TS interface is missing them, causing `useStudentDashboard` to define its own duplicate `StudentInfo` type.

**Files:**
- Modify: `frontend/apps/student/src/hooks/useStudentInfo.ts`
- Modify (test): `frontend/apps/student/src/hooks/__tests__/useStudentInfo.test.ts`

- [ ] **Step 1: Write the failing test**

Open `frontend/apps/student/src/hooks/__tests__/useStudentInfo.test.ts` and add at the end of the describe block:

```typescript
it("test_useStudentInfo_when_api_returns_enrolledClasses_then_types_include_them", () => {
  // This is a type-level test — if it compiles, it passes.
  const info: import("../useStudentInfo").StudentInfo = {
    id: "abc",
    firstName: "Jane",
    email: "jane@test.com",
    gradeName: "Grade 9",
    curriculumName: "Cambridge IGCSE",
    schoolId: "school-1",
    enrolledClasses: [
      { classId: "cls-1", className: "Math 9B", subjectId: "sub-1", subjectName: "Mathematics", gradeName: "Grade 9" },
    ],
  };
  expect(info.id).toBe("abc");
  expect(info.enrolledClasses).toHaveLength(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test --filter student -- --testPathPattern="useStudentInfo" 2>&1 | tail -20
```

Expected: TypeScript compile error — `id` and `enrolledClasses` do not exist on type `StudentInfo`.

- [ ] **Step 3: Update `useStudentInfo.ts`**

Replace the `StudentInfo` interface in `frontend/apps/student/src/hooks/useStudentInfo.ts`:

```typescript
export interface EnrolledClass {
  classId: string;
  className: string;
  subjectId: string;
  subjectName: string;
  gradeName: string;
}

export interface StudentInfo {
  id: string;
  firstName: string;
  lastName?: string;
  email: string;
  gradeName: string;
  curriculumName: string;
  schoolId: string;
  classId?: string | null;
  isEnrolled?: boolean;
  enrolledClasses: EnrolledClass[];
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && pnpm test --filter student -- --testPathPattern="useStudentInfo" 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/student/src/hooks/useStudentInfo.ts \
        frontend/apps/student/src/hooks/__tests__/useStudentInfo.test.ts
git commit -m "feat(student): add id and enrolledClasses to StudentInfo interface"
```

---

## Task 2: Create `useStudentAssessments` hook

**Files:**
- Create: `frontend/apps/student/src/hooks/useStudentAssessments.ts`
- Create: `frontend/apps/student/src/hooks/__tests__/useStudentAssessments.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/apps/student/src/hooks/__tests__/useStudentAssessments.test.ts`:

```typescript
/**
 * @jest-environment jsdom
 */
import { renderHook, waitFor } from "@testing-library/react";
import { useStudentAssessments } from "../useStudentAssessments";

jest.mock("@kaihle/auth", () => ({
  apiClient: { get: jest.fn() },
}));

import { apiClient } from "@kaihle/auth";
const mockGet = apiClient.get as jest.Mock;

// Wrap in QueryClientProvider
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const TEACHER_ASSESSMENT = {
  id: "assess-1",
  class_id: "cls-1",
  title: "Chapter 3 Quiz",
  assessment_type: "PROGRESS_CHECK",
  is_system_generated: false,
  status: "ACTIVE",
  question_count: 10,
  deadline: null,
  published_at: "2026-04-01T00:00:00Z",
};

const DIAGNOSTIC_ASSESSMENT = {
  id: "assess-2",
  class_id: "cls-1",
  title: "Onboarding Diagnostic",
  assessment_type: "DIAGNOSTIC",
  is_system_generated: true,
  status: "ACTIVE",
  question_count: 20,
  deadline: null,
  published_at: "2026-04-01T00:00:00Z",
};

describe("useStudentAssessments", () => {
  beforeEach(() => jest.clearAllMocks());

  it("test_useStudentAssessments_when_empty_classIds_then_returns_empty_results", () => {
    mockGet.mockResolvedValue({ data: { data: [] } });
    const { result } = renderHook(
      () => useStudentAssessments([], "student-1"),
      { wrapper },
    );
    expect(result.current.diagnostics).toEqual([]);
    expect(result.current.teacherAssessments).toEqual([]);
    expect(result.current.newCount).toBe(0);
  });

  it("test_useStudentAssessments_when_has_teacher_assessment_then_separates_from_diagnostics", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT, DIAGNOSTIC_ASSESSMENT] } });
      }
      // attempts endpoint
      return Promise.resolve({ data: { data: [] } });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(result.current.teacherAssessments).toHaveLength(1);
    expect(result.current.teacherAssessments[0].id).toBe("assess-1");
    expect(result.current.diagnostics).toHaveLength(1);
    expect(result.current.diagnostics[0].id).toBe("assess-2");
  });

  it("test_useStudentAssessments_when_active_teacher_assessment_not_attempted_then_newCount_is_1", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT] } });
      }
      return Promise.resolve({ data: { data: [] } });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.newCount).toBe(1);
  });

  it("test_useStudentAssessments_when_attempt_submitted_then_newCount_is_0", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT] } });
      }
      // attempts endpoint — student already submitted
      return Promise.resolve({
        data: {
          data: [{
            attempt_id: "att-1",
            assessment_id: "assess-1",
            status: "SUBMITTED",
            score: 0.8,
          }],
        },
      });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.newCount).toBe(0);
    expect(result.current.teacherAssessments[0].attemptStatus).toBe("COMPLETED");
  });

  it("test_useStudentAssessments_when_attempt_in_progress_then_attemptStatus_is_IN_PROGRESS", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT] } });
      }
      return Promise.resolve({
        data: {
          data: [{
            attempt_id: "att-1",
            assessment_id: "assess-1",
            status: "IN_PROGRESS",
            score: null,
          }],
        },
      });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.teacherAssessments[0].attemptStatus).toBe("IN_PROGRESS");
    // IN_PROGRESS still counts as new (student hasn't finished)
    expect(result.current.newCount).toBe(0);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && pnpm test --filter student -- --testPathPattern="useStudentAssessments" 2>&1 | tail -20
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create the hook**

Create `frontend/apps/student/src/hooks/useStudentAssessments.ts`:

```typescript
import { useQueries, useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

interface AssessmentApiResponse {
  id: string;
  class_id: string;
  title: string;
  assessment_type: string;
  is_system_generated: boolean;
  status: string;
  question_count: number;
  deadline: string | null;
  published_at: string | null;
}

interface AssessmentsPage {
  data: AssessmentApiResponse[];
}

interface AttemptHistoryItem {
  attempt_id: string;
  assessment_id: string;
  status: string;
  score: number | null;
}

interface AttemptsPage {
  data: AttemptHistoryItem[];
}

export type AttemptStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";

export interface AssessmentItem {
  id: string;
  classId: string;
  title: string;
  assessmentType: "DIAGNOSTIC" | "PROGRESS_CHECK";
  isSystemGenerated: boolean;
  status: "DRAFT" | "ACTIVE" | "CLOSED";
  questionCount: number;
  deadline: string | null;
  publishedAt: string | null;
  attemptStatus: AttemptStatus;
  attemptId: string | null;
  score: number | null;
}

export interface UseStudentAssessmentsResult {
  diagnostics: AssessmentItem[];
  teacherAssessments: AssessmentItem[];
  newCount: number;
  isPending: boolean;
  isError: boolean;
}

export function useStudentAssessments(
  classIds: string[],
  studentId: string | undefined,
): UseStudentAssessmentsResult {
  const assessmentQueries = useQueries({
    queries: classIds.map((classId) => ({
      queryKey: ["student", "assessments", "class", classId] as const,
      queryFn: async (): Promise<AssessmentApiResponse[]> => {
        const res = await apiClient.get<AssessmentsPage>(
          `/api/v1/classes/${classId}/assessments`,
          { params: { page: 1, page_size: 50 } },
        );
        return res.data.data;
      },
      staleTime: 2 * 60 * 1000,
      enabled: classIds.length > 0,
    })),
  });

  const attemptsQuery = useQuery({
    queryKey: ["student", "attempts", studentId] as const,
    queryFn: async (): Promise<AttemptHistoryItem[]> => {
      const res = await apiClient.get<AttemptsPage>(
        `/api/v1/students/${studentId}/attempts`,
        { params: { page: 1, page_size: 100 } },
      );
      return res.data.data;
    },
    staleTime: 2 * 60 * 1000,
    enabled: !!studentId,
  });

  const isPending =
    (classIds.length > 0 && assessmentQueries.some((q) => q.isPending)) ||
    (!!studentId && attemptsQuery.isPending);
  const isError =
    assessmentQueries.some((q) => q.isError) || attemptsQuery.isError;

  // Build attempt lookup: assessment_id → attempt
  const attemptMap = new Map<string, AttemptHistoryItem>();
  for (const a of attemptsQuery.data ?? []) {
    attemptMap.set(a.assessment_id, a);
  }

  function toAttemptStatus(
    apiStatus: string,
    attempt: AttemptHistoryItem | undefined,
  ): AttemptStatus {
    if (!attempt) return "NOT_STARTED";
    if (attempt.status === "SUBMITTED") return "COMPLETED";
    return "IN_PROGRESS";
  }

  const allAssessments: AssessmentItem[] = assessmentQueries
    .flatMap((q) => q.data ?? [])
    .map((a): AssessmentItem => {
      const attempt = attemptMap.get(a.id);
      return {
        id: a.id,
        classId: a.class_id,
        title: a.title,
        assessmentType: a.assessment_type as AssessmentItem["assessmentType"],
        isSystemGenerated: a.is_system_generated,
        status: a.status as AssessmentItem["status"],
        questionCount: a.question_count,
        deadline: a.deadline,
        publishedAt: a.published_at,
        attemptStatus: toAttemptStatus(a.status, attempt),
        attemptId: attempt?.attempt_id ?? null,
        score: attempt?.score ?? null,
      };
    });

  const diagnostics = allAssessments.filter((a) => a.isSystemGenerated);
  const teacherAssessments = allAssessments.filter((a) => !a.isSystemGenerated);

  // Badge: ACTIVE teacher assessments the student hasn't started yet
  const newCount = teacherAssessments.filter(
    (a) => a.status === "ACTIVE" && a.attemptStatus === "NOT_STARTED",
  ).length;

  return { diagnostics, teacherAssessments, newCount, isPending, isError };
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && pnpm test --filter student -- --testPathPattern="useStudentAssessments" 2>&1 | tail -15
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/student/src/hooks/useStudentAssessments.ts \
        frontend/apps/student/src/hooks/__tests__/useStudentAssessments.test.ts
git commit -m "feat(student): add useStudentAssessments hook with badge count and attempt status"
```

---

## Task 3: Add `assessmentBadge` prop to `StudentLayout`

**Files:**
- Modify: `frontend/packages/ui/src/layouts/StudentLayout.tsx`

- [ ] **Step 1: Add `assessmentBadge` to `StudentLayoutProps`**

In `frontend/packages/ui/src/layouts/StudentLayout.tsx`, in the `StudentLayoutProps` interface, add after `studyPlanBadge`:

```typescript
  assessmentBadge?: number; // count of new ACTIVE assessments not yet started
```

- [ ] **Step 2: Destructure the new prop**

In the `StudentLayout` function signature, add `assessmentBadge` alongside `studyPlanBadge`:

```typescript
export function StudentLayout({
  children,
  activeNav,
  classes = [],
  studentName,
  gradeName,
  curriculumName,
  onLogout,
  studyPlanBadge,
  assessmentBadge,
}: StudentLayoutProps) {
```

- [ ] **Step 3: Wire the badge to the Assessments nav item**

In the `showBadge` logic inside the `.map(({ key, label, Icon }) => {` block, replace:

```typescript
const showBadge =
  key === "study-plans" && studyPlanBadge && studyPlanBadge > 0;
```

with:

```typescript
const badgeCount =
  key === "study-plans"
    ? studyPlanBadge
    : key === "assessments"
      ? assessmentBadge
      : undefined;
const showBadge = !!badgeCount && badgeCount > 0;
```

Then replace the badge span:

```typescript
{showBadge && (
  <span className="ml-auto bg-brand-primary text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full leading-none">
    {badgeCount}
  </span>
)}
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && pnpm typecheck 2>&1 | tail -20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/ui/src/layouts/StudentLayout.tsx
git commit -m "feat(ui): add assessmentBadge prop to StudentLayout sidebar"
```

---

## Task 4: Enhance `useStudentLayoutProps` with assessment badge

**Files:**
- Modify: `frontend/apps/student/src/hooks/useStudentLayoutProps.ts`
- Modify: `frontend/apps/student/src/hooks/__tests__/useStudentLayoutProps.test.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/apps/student/src/hooks/__tests__/useStudentLayoutProps.test.ts`, add at the end of the describe block (before the closing `}`):

```typescript
  it("test_useStudentLayoutProps_when_student_has_new_assessments_then_returns_assessmentBadgeCount", () => {
    mockUseStudentInfo.mockReturnValue({
      data: {
        id: "stu-1",
        firstName: "Jane",
        lastName: "Doe",
        gradeName: "Grade 9",
        curriculumName: "Cambridge IGCSE",
        enrolledClasses: [{ classId: "cls-1", className: "Math 9B", subjectId: "sub-1", subjectName: "Mathematics", gradeName: "Grade 9" }],
      },
      isLoading: false,
    });
    mockUseMyClasses.mockReturnValue({
      data: [{ id: "cls-1", name: "Math 9B", subjectName: "Mathematics", subjectId: "sub-1", onboardingDiagnosticStatus: "COMPLETED", diagnosticAttemptId: null }],
      isLoading: false,
    });

    // Mock useStudentAssessments
    const mockUseStudentAssessments = require("../useStudentAssessments").useStudentAssessments as jest.Mock;
    mockUseStudentAssessments.mockReturnValue({
      newCount: 3,
      isPending: false,
      isError: false,
    });

    const { result } = renderHook(() => useStudentLayoutProps());
    expect(result.current.assessmentBadgeCount).toBe(3);
  });
```

Also add this mock at the top of the test file, alongside the other jest.mock calls:

```typescript
jest.mock("../useStudentAssessments", () => ({
  useStudentAssessments: jest.fn(() => ({ newCount: 0, isPending: false, isError: false })),
}));
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test --filter student -- --testPathPattern="useStudentLayoutProps" 2>&1 | tail -20
```

Expected: FAIL — `assessmentBadgeCount` is not a property.

- [ ] **Step 3: Update `useStudentLayoutProps.ts`**

Replace the entire file content:

```typescript
import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "./useStudentInfo";
import { useMyClasses, type StudentClassResponse } from "./useMyClasses";
import { useStudentAssessments } from "./useStudentAssessments";

export interface SidebarClass {
  id: string;
  name: string;
  subjectName: string;
  subjectId: string;
  diagnosticStatus: "PENDING" | "IN_PROGRESS" | "COMPLETED";
  diagnosticAttemptId: string | null;
}

export interface StudentLayoutProps {
  studentName: string;
  gradeName: string;
  curriculumName: string;
  sidebarClasses: SidebarClass[];
  onLogout: () => void;
  isLoading: boolean;
  assessmentBadgeCount: number;
}

export function useStudentLayoutProps(): StudentLayoutProps {
  const { logout } = useAuth();
  const { data: studentInfo, isLoading: isInfoLoading } = useStudentInfo();
  const { data: classesData, isLoading: isClassesLoading } = useMyClasses();

  const classIds = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => cls.id,
  );

  const { newCount } = useStudentAssessments(classIds, studentInfo?.id);

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse): SidebarClass => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  return {
    studentName,
    gradeName,
    curriculumName,
    sidebarClasses,
    onLogout: logout,
    isLoading: isInfoLoading || isClassesLoading,
    assessmentBadgeCount: newCount,
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && pnpm test --filter student -- --testPathPattern="useStudentLayoutProps" 2>&1 | tail -15
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/student/src/hooks/useStudentLayoutProps.ts \
        frontend/apps/student/src/hooks/__tests__/useStudentLayoutProps.test.ts
git commit -m "feat(student): enhance useStudentLayoutProps with assessmentBadgeCount"
```

---

## Task 5: Rebuild `Assessments.tsx`

**Files:**
- Modify: `frontend/apps/student/src/pages/assessments/Assessments.tsx`

- [ ] **Step 1: Replace the entire file**

```typescript
import { Link } from "react-router-dom";
import { ClipboardList, Clock, CheckCircle2, Circle } from "lucide-react";
import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { useStudentAssessments, type AssessmentItem, type AttemptStatus } from "../../hooks/useStudentAssessments";
import { useMyClasses } from "../../hooks/useMyClasses";

// ── Helpers ──────────────────────────────────────────────────

function formatDeadline(deadline: string | null): string {
  if (!deadline) return "No deadline";
  return new Date(deadline).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function StatusBadge({ status }: { status: AttemptStatus }) {
  const config: Record<AttemptStatus, { label: string; className: string; Icon: typeof Circle }> = {
    NOT_STARTED: { label: "Not started", className: "bg-gray-100 text-brand-body", Icon: Circle },
    IN_PROGRESS: { label: "In progress", className: "bg-brand-amber-light text-brand-amber", Icon: Clock },
    COMPLETED: { label: "Completed", className: "bg-brand-green-light text-brand-green", Icon: CheckCircle2 },
  };
  const { label, className, Icon } = config[status];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${className}`}>
      <Icon className="w-3 h-3" aria-hidden="true" />
      {label}
    </span>
  );
}

// ── Teacher assessment card ───────────────────────────────────

function TeacherAssessmentCard({
  assessment,
  className: classLabel,
}: {
  assessment: AssessmentItem;
  className: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-role-student-border p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-wide text-brand-muted mb-1">
            {classLabel}
          </p>
          <h3 className="font-display font-bold text-lg text-brand-ink leading-snug">
            {assessment.title}
          </h3>
        </div>
        <StatusBadge status={assessment.attemptStatus} />
      </div>

      <div className="flex items-center gap-4 font-sans text-sm text-brand-body">
        <span>{assessment.questionCount} questions</span>
        <span>·</span>
        <span>{formatDeadline(assessment.deadline)}</span>
      </div>

      {assessment.attemptStatus === "COMPLETED" && assessment.score !== null && (
        <p className="font-sans text-sm font-semibold text-brand-green">
          Score: {Math.round(assessment.score * 100)}%
        </p>
      )}
    </div>
  );
}

// ── Diagnostic card ───────────────────────────────────────────

function DiagnosticCard({
  assessment,
  className: classLabel,
}: {
  assessment: AssessmentItem;
  className: string;
}) {
  const isCompleted = assessment.attemptStatus === "COMPLETED";
  const attemptRoute = assessment.attemptId
    ? isCompleted
      ? `/student/assessments/${assessment.attemptId}/results`
      : `/student/assessments/${assessment.attemptId}/take`
    : null;

  return (
    <div className="bg-white rounded-xl border border-role-student-border p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-brand-green-light flex items-center justify-center flex-shrink-0">
          <ClipboardList className="w-5 h-5 text-brand-primary" aria-hidden="true" />
        </div>
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-wide text-brand-muted mb-0.5">
            {classLabel} · Get started
          </p>
          <h3 className="font-display font-bold text-base text-brand-ink">
            {assessment.title}
          </h3>
          <p className="font-sans text-xs text-brand-body mt-0.5">
            {assessment.questionCount} questions · Unlocks class content
          </p>
        </div>
      </div>

      {attemptRoute && (
        <Link
          to={attemptRoute}
          className="flex-shrink-0 bg-brand-primary text-white font-sans text-sm font-semibold px-4 py-2 rounded-full hover:opacity-90 transition-opacity focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {isCompleted ? "View results" : assessment.attemptStatus === "IN_PROGRESS" ? "Continue" : "Start"}
        </Link>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────

export function Assessments() {
  const layout = useStudentLayoutProps();
  const { data: classesData } = useMyClasses();

  // Build classId → className map for card labels
  const classMap = new Map<string, string>(
    (Array.isArray(classesData) ? classesData : []).map((c) => [c.id, c.name]),
  );

  const {
    diagnostics,
    teacherAssessments,
    newCount,
    isPending,
  } = useStudentAssessments(
    layout.sidebarClasses.map((c) => c.id),
    undefined, // studentId not needed here — useStudentLayoutProps already called it
  );

  // Re-use cached student id from useStudentAssessments in useStudentLayoutProps
  // Pass undefined here since the hook internally resolves via useStudentInfo cache

  const pendingDiagnostics = diagnostics.filter(
    (d) => d.attemptStatus !== "COMPLETED",
  );

  return (
    <StudentLayout
      activeNav="assessments"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      onLogout={layout.onLogout}
      assessmentBadge={newCount}
    >
      <div className="space-y-8">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Assessments
        </h1>

        {/* ── Loading skeleton ─────────────────── */}
        {isPending && (
          <div className="animate-pulse space-y-3">
            <div className="h-20 bg-brand-border rounded-xl w-full" />
            <div className="h-20 bg-brand-border rounded-xl w-full" />
          </div>
        )}

        {!isPending && (
          <>
            {/* ── Get Started section (pending diagnostics) ── */}
            {pendingDiagnostics.length > 0 && (
              <section aria-labelledby="get-started-heading">
                <h2
                  id="get-started-heading"
                  className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
                >
                  Get Started
                </h2>
                <div className="space-y-3">
                  {pendingDiagnostics.map((d) => (
                    <DiagnosticCard
                      key={d.id}
                      assessment={d}
                      className={classMap.get(d.classId) ?? "Class"}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* ── Teacher assessments ──────────────── */}
            <section aria-labelledby="teacher-assessments-heading">
              <h2
                id="teacher-assessments-heading"
                className="font-sans text-xs font-bold uppercase tracking-widest text-brand-muted mb-3"
              >
                Assigned by teacher
              </h2>

              {teacherAssessments.length === 0 ? (
                <div className="bg-white rounded-xl border border-role-student-border p-12 text-center">
                  <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
                    No assessments yet
                  </h3>
                  <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto mb-4">
                    Your teacher will assign assessments here when ready.
                  </p>
                  <Link
                    to="/student/my-progress"
                    className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
                  >
                    See your progress so far →
                  </Link>
                </div>
              ) : (
                <div className="space-y-3">
                  {teacherAssessments.map((a) => (
                    <TeacherAssessmentCard
                      key={a.id}
                      assessment={a}
                      className={classMap.get(a.classId) ?? "Class"}
                    />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </StudentLayout>
  );
}
```

**Note on `studentId` in the Assessments page:** The `useStudentAssessments` hook called from `useStudentLayoutProps` already populates the `["student", "attempts", studentId]` cache. To reuse that cache on this page we need the same `studentId`. Import `useStudentInfo` to get it:

Add this import and usage:

```typescript
import { useStudentInfo } from "../../hooks/useStudentInfo";
// inside Assessments():
const { data: studentInfo } = useStudentInfo();
// pass to useStudentAssessments:
const { diagnostics, teacherAssessments, newCount, isPending } = useStudentAssessments(
  layout.sidebarClasses.map((c) => c.id),
  studentInfo?.id,
);
```

Remove the `undefined` placeholder and `// Re-use cached...` comment block from the step above.

- [ ] **Step 2: Type-check**

```bash
cd frontend && pnpm typecheck 2>&1 | grep "assessments/Assessments" | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/student/src/pages/assessments/Assessments.tsx
git commit -m "feat(student): rebuild Assessments page with real data, diagnostic section, and teacher list"
```

---

## Task 6: Fix `useStudentDashboard` for multi-class support

The hook currently uses `studentInfoQuery.data?.classId` (a single legacy field). Students enrolled in 2+ classes only see one class's assessments on the dashboard.

**Files:**
- Modify: `frontend/apps/student/src/hooks/useStudentDashboard.ts`

- [ ] **Step 1: Replace the file**

```typescript
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useStudentInfo } from "./useStudentInfo";
import { useStudentAssessments } from "./useStudentAssessments";

interface StudyPlan {
  id: string;
  title: string;
  status: "ACTIVE" | "IN_PROGRESS" | "COMPLETED";
}

interface StudyPlansResponse {
  data: StudyPlan[];
}

interface DashboardData {
  studyPlans: StudyPlan[];
  assessmentCount: number; // total ACTIVE teacher assessments
}

interface UseStudentDashboardResult {
  data: DashboardData | undefined;
  isPending: boolean;
  isError: boolean;
  errMessage: string | undefined;
  refetch: () => Promise<void>;
}

export function useStudentDashboard(): UseStudentDashboardResult {
  const studentInfoQuery = useStudentInfo();

  const classIds = (studentInfoQuery.data?.enrolledClasses ?? []).map(
    (c) => c.classId,
  );

  const studyPlansQuery = useQuery({
    queryKey: ["student", "study-plans"] as const,
    queryFn: async (): Promise<StudyPlan[]> => {
      const res = await apiClient.get<StudyPlansResponse>(
        `/api/v1/students/me/study-plans?status=active,in_progress&limit=10`,
      );
      return res.data.data;
    },
    enabled: studentInfoQuery.data?.isEnrolled === true,
  });

  const { teacherAssessments, isPending: assessmentsPending, isError: assessmentsError } =
    useStudentAssessments(classIds, studentInfoQuery.data?.id);

  const isPending =
    studentInfoQuery.isPending ||
    studyPlansQuery.isPending ||
    assessmentsPending;

  const isError =
    studentInfoQuery.isError ||
    studyPlansQuery.isError ||
    assessmentsError;

  const errMessage =
    studentInfoQuery.error?.message ||
    studyPlansQuery.error?.message;

  const data = studentInfoQuery.data
    ? {
        studyPlans: studyPlansQuery.data ?? [],
        assessmentCount: teacherAssessments.filter((a) => a.status === "ACTIVE").length,
      }
    : undefined;

  return {
    data,
    isPending,
    isError,
    errMessage,
    refetch: async () => {
      await Promise.all([
        studentInfoQuery.refetch(),
        studyPlansQuery.refetch(),
      ]);
    },
  };
}
```

- [ ] **Step 2: Fix `StudentDashboard.tsx` to match the updated `DashboardData` shape**

Open `frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx`. The dashboard currently reads `data.assessments` (an array). After this change it becomes `data.assessmentCount` (a number). Update any references:

Find and replace in `StudentDashboard.tsx`:
- `data.assessments` → `data.assessmentCount`
- Wherever it was rendering `assessments.map(...)` on the dashboard, replace with a count display: `{data.assessmentCount} active assessment{data.assessmentCount !== 1 ? "s" : ""}`

- [ ] **Step 3: Type-check**

```bash
cd frontend && pnpm typecheck 2>&1 | grep -i "dashboard\|studentDashboard" | head -20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/student/src/hooks/useStudentDashboard.ts \
        frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx
git commit -m "fix(student): fetch assessments across all enrolled classes in dashboard"
```

---

## Task 7: Switch all pages to `useStudentLayoutProps`

Each of these pages manually calls `useStudentInfo` + `useMyClasses` + manually maps sidebar props. Replace with `useStudentLayoutProps` in all five pages.

**Files:**
- Modify: `frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx`
- Modify: `frontend/apps/student/src/pages/my-progress/MyProgress.tsx`
- Modify: `frontend/apps/student/src/pages/study-plans/StudyPlans.tsx`
- Modify: `frontend/apps/student/src/pages/settings/StudentSettings.tsx`
- Modify: `frontend/apps/student/src/pages/assessments/TakeAssessmentPage.tsx`

The pattern to apply in each file is:

**Remove:**
```typescript
import { useStudentInfo } from "../../hooks/useStudentInfo";
import { useMyClasses, type StudentClassResponse } from "../../hooks/useMyClasses";
// ... and all the manual mapping:
const { data: studentInfo } = useStudentInfo();
const { data: classesData } = useMyClasses();
const firstName = studentInfo?.firstName ?? "";
const lastName = studentInfo?.lastName ?? "";
const studentName = [firstName, lastName].filter(Boolean).join(" ") || "Student";
const gradeName = studentInfo?.gradeName ?? "";
const curriculumName = studentInfo?.curriculumName ?? "";
const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
  (cls: StudentClassResponse) => ({ ... }),
);
```

**Add:**
```typescript
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
// inside component:
const layout = useStudentLayoutProps();
```

**Update `StudentLayout` props:**
```typescript
<StudentLayout
  activeNav="<the-page-key>"
  studentName={layout.studentName}
  gradeName={layout.gradeName}
  curriculumName={layout.curriculumName}
  classes={layout.sidebarClasses}
  onLogout={layout.onLogout}
  assessmentBadge={layout.assessmentBadgeCount}
>
```

- [ ] **Step 1: Update `StudentDashboard.tsx`**

Apply the pattern above. The dashboard also calls `useStudentDashboard()` — keep that. Remove `useStudentInfo` and `useMyClasses` imports and manual mapping. `activeNav="home"`.

- [ ] **Step 2: Update `MyProgress.tsx`**

Apply the pattern. Keep `useStudentGapMap`. Remove `useStudentInfo`, `useMyClasses` manual block. `activeNav="progress"`.

Note: `MyProgress.tsx` uses `classesData` to get class IDs for the gap map subject selector. After switching, use `layout.sidebarClasses` instead of `classesData`.

- [ ] **Step 3: Update `StudyPlans.tsx`**

Apply the pattern. Keep `useMyStudyPlans`. Remove `useStudentInfo`, `useMyClasses`. `activeNav="study-plans"`.

- [ ] **Step 4: Update `StudentSettings.tsx`**

Apply the pattern. Remove `useStudentInfo`, `useMyClasses`. `activeNav` — check current value or add `"settings"` if it exists on `StudentNavItem`. If `"settings"` is not a valid nav item, pass `"home"` as fallback (settings is accessible via avatar click, not sidebar nav).

- [ ] **Step 5: Update `TakeAssessmentPage.tsx`**

Apply the pattern. Remove `useStudentInfo`, `useMyClasses`. Keep `useAttempt` and all assessment-taking logic. The `activeNav` for this page can be `"assessments"`.

- [ ] **Step 6: Type-check all**

```bash
cd frontend && pnpm typecheck 2>&1 | tail -20
```

Expected: no errors.

- [ ] **Step 7: Run full test suite**

```bash
cd frontend && pnpm test 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add \
  frontend/apps/student/src/pages/dashboard/StudentDashboard.tsx \
  frontend/apps/student/src/pages/my-progress/MyProgress.tsx \
  frontend/apps/student/src/pages/study-plans/StudyPlans.tsx \
  frontend/apps/student/src/pages/settings/StudentSettings.tsx \
  frontend/apps/student/src/pages/assessments/TakeAssessmentPage.tsx
git commit -m "refactor(student): switch all pages to useStudentLayoutProps"
```

---

## Task 8: Final verification and PR

- [ ] **Step 1: Full typecheck**

```bash
cd frontend && pnpm typecheck 2>&1 | tail -20
```

Expected: no errors.

- [ ] **Step 2: Full test suite**

```bash
cd frontend && pnpm test 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 3: Lint**

```bash
cd frontend && pnpm lint 2>&1 | tail -20
```

Expected: no errors.

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin student/assessments-page-fix
gh pr create \
  --title "student/assessments-page-fix" \
  --body "$(cat <<'EOF'
## What this fixes

- Assessments page was a static empty state — now fetches and displays real assessments
- Dashboard only fetched one class's assessments — now covers all enrolled classes
- Added assessment badge (red count dot) to sidebar Assessments nav item
- All student pages were duplicating useStudentInfo + useMyClasses calls manually — now use useStudentLayoutProps

## How to verify

1. Log in as a student enrolled in a class where the teacher has published an assessment
2. Navigate to Assessments — should see teacher assessments listed with subject, title, deadline, question count, status
3. Sidebar should show a badge count on Assessments nav item if any assessments are ACTIVE and NOT_STARTED
4. If any class has a pending diagnostic, it appears in the Get Started section above teacher assessments
5. Navigate to Dashboard — assessments count should reflect all enrolled classes

## Scope note

Teacher assessment Start button is not implemented — no backend endpoint exists to create a Tier 2 attempt. Cards show metadata and status only. This is intentional per YAGNI.
EOF
)"
```
