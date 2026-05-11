# Frontend API Call Discipline

## Rule: Each page/tab fetches only what it needs

Every page or tab component MUST only call the API endpoints required for its own content.

**PROHIBITED:**

- Using a composite dashboard hook (e.g. `useTeacherDashboard`) in a sub-page just to read one field (e.g. class name for a breadcrumb).
- Calling a hook that issues multiple sub-queries when a single targeted endpoint exists.
- Sharing a data-loading hook across tabs in a feature area when each tab has distinct data needs.

**REQUIRED:**

- Use the most targeted endpoint available. If you need a class name, call `/api/v1/classes/:id` — not a hook that loads all teacher classes + grades + subjects + per-class summaries.
- Tab pages inside a class context (gap-map, assessments, lesson-plans, study-plan) each make only the calls their content requires. They do NOT call class-list or dashboard endpoints.
- If the same data (e.g. class name for breadcrumb) is needed across multiple sub-pages, create a shared **single-resource** hook (e.g. `useClass(classId)`) that calls exactly one targeted endpoint.

## Example — correct vs wrong

```
// WRONG: loads grades + subjects + all classes + per-class summaries
const { data: dashboardData } = useTeacherDashboard(schoolId);
const cls = dashboardData?.classes.find(c => c.id === classId);
const breadcrumbName = cls?.name;

// CORRECT: one call, one resource
const { data: cls } = useClass(classId);   // GET /api/v1/classes/:id
const breadcrumbName = cls?.name;
```

## Applies to all five apps

This rule applies to teacher, student, parent, school-admin, and kaihle-admin apps. Each feature area (class detail, student profile, assessment flow, etc.) is responsible for its own data — it does not "borrow" a parent page's composite hook.
