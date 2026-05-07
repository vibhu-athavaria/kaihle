# ST-E — Assessment Results: Split Diagnostic vs Formative Copy
Executor: Coding agent
Branch: `st-e-results-page-split` (branch from `main`)

---

## Context

`AssessmentResultsPage.tsx` shows "Diagnostic complete! Head back to see what's now unlocked." for every assessment submission. This copy is wrong for Tier 2 (teacher-created formative) assessments.

The fix is to branch on `assessment_type`. The `AttemptResultResponse` already contains this field — read `src/hooks/useAttempt.ts` to confirm the type shape before making changes.

No backend changes needed. This is a frontend-only change.

---

## Files to Modify

- `src/pages/assessments/AssessmentResultsPage.tsx`
- `src/hooks/useAttempt.ts` — verify `AttemptResultResponse` contains `assessment_type`; add it if missing

---

## Task 1 — Verify AttemptResultResponse has assessment_type

**File:** `src/hooks/useAttempt.ts`

Read this file. Find the `AttemptResultResponse` interface. Check if `assessment_type` is present.

If it is NOT present, add it:
```ts
export interface AttemptResultResponse {
  // ... existing fields ...
  assessment_type: "DIAGNOSTIC" | "PROGRESS_CHECK";  // add this
}
```

If it IS already present, proceed to Task 2 without changes.

The backend `AttemptResultResponse` schema is in `backend/app/schemas/attempts.py`. Read it to confirm the field name used in the API response. Use exactly that field name.

---

## Task 2 — Split the result screen by assessment type

**File:** `src/pages/assessments/AssessmentResultsPage.tsx`

The page currently has a single hardcoded banner:
```tsx
<div className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center">
  <p className="font-sans font-semibold text-sm text-brand-green">
    Diagnostic complete!{" "}
    <span className="font-normal">Head back to see what's now unlocked.</span>
  </p>
</div>
```

And a single CTA:
```tsx
<button onClick={() => navigate("/student/dashboard")}>
  Back to Dashboard
</button>
```

Replace both with branched content based on `result.assessment_type`.

**For `DIAGNOSTIC` type — keep existing behavior:**
```tsx
{/* Banner */}
<div className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center" role="status" aria-live="polite">
  <p className="font-sans font-semibold text-sm text-brand-green">
    Diagnostic complete!{" "}
    <span className="font-normal">Head back to see what's now unlocked.</span>
  </p>
</div>

{/* CTA */}
<button
  type="button"
  onClick={() => navigate("/student/dashboard")}
  className="w-full bg-brand-primary text-white px-6 py-3 rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
>
  Back to Dashboard
</button>
```

**For `PROGRESS_CHECK` type (formative assessment):**
```tsx
{/* Banner */}
<div className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center" role="status" aria-live="polite">
  <p className="font-sans font-semibold text-sm text-brand-green">
    Assessment submitted.{" "}
    <span className="font-normal">Your progress has been updated.</span>
  </p>
</div>

{/* CTA — takes student to My Progress, not Dashboard */}
<button
  type="button"
  onClick={() => navigate("/student/my-progress")}
  className="w-full bg-brand-primary text-white px-6 py-3 rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
>
  View my progress →
</button>
```

**Implementation pattern — replace the hardcoded banner and CTA with:**

```tsx
const isDiagnostic = result.assessment_type === "DIAGNOSTIC";

// Banner
{isDiagnostic ? (
  <DiagnosticBanner />
) : (
  <FormativeBanner />
)}

// Score ring — unchanged, same for both types

// Correct count — unchanged, same for both types

// CTA
<button
  type="button"
  onClick={() => navigate(isDiagnostic ? "/student/dashboard" : "/student/my-progress")}
  className="w-full bg-brand-primary text-white px-6 py-3 rounded-full font-sans font-semibold text-sm hover:bg-brand-dark transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
>
  {isDiagnostic ? "Back to Dashboard" : "View my progress →"}
</button>
```

Extract `DiagnosticBanner` and `FormativeBanner` as small inline components at the bottom of the file (not exported):

```tsx
function DiagnosticBanner() {
  return (
    <div className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center" role="status" aria-live="polite">
      <p className="font-sans font-semibold text-sm text-brand-green">
        Diagnostic complete!{" "}
        <span className="font-normal">Head back to see what's now unlocked.</span>
      </p>
    </div>
  );
}

function FormativeBanner() {
  return (
    <div className="w-full bg-brand-green-light border border-brand-mid rounded-xl px-4 py-3 text-center" role="status" aria-live="polite">
      <p className="font-sans font-semibold text-sm text-brand-green">
        Assessment submitted.{" "}
        <span className="font-normal">Your progress has been updated.</span>
      </p>
    </div>
  );
}
```

---

## Task 3 — Handle missing assessment_type gracefully

If `result.assessment_type` is `undefined` or `null` (e.g. older API responses), default to diagnostic behavior:

```ts
const isDiagnostic = !result.assessment_type || result.assessment_type === "DIAGNOSTIC";
```

This ensures no regression for any existing diagnostic attempts in the system.

---

## Acceptance Criteria

- [ ] `AttemptResultResponse` type includes `assessment_type: "DIAGNOSTIC" | "PROGRESS_CHECK"`
- [ ] Diagnostic assessment results show "Diagnostic complete!" banner + "Back to Dashboard" CTA
- [ ] Formative assessment results show "Assessment submitted." banner + "View my progress →" CTA
- [ ] "View my progress →" navigates to `/student/my-progress`
- [ ] Missing/undefined `assessment_type` defaults to diagnostic behavior (no regression)
- [ ] Score ring and correct count display identically for both types
- [ ] TypeScript compiles with zero errors (`pnpm typecheck`)
- [ ] No ESLint errors (`pnpm lint`)
