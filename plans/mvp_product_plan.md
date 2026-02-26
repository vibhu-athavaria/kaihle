# Kaihle — MVP Roadmap
## Product Plan v1.0 · February 2026

**Stack:** FastAPI · PostgreSQL · pgvector · Redis · Celery · React + Vite · Docker · AWS S3/MinIO · Manim · Google Gemini API
**Coding Agent Rules:** Read `AGENTS.md` in full before writing any code. This document defines what to build. AGENTS.md defines how to build it.

---

## How to Use This Document

- Each phase is self-contained. Read only the phase you are building.
- Every model, endpoint, file path, and acceptance criterion is **explicit**.
- Do not infer or improvise anything not stated here.
- Do not begin a new phase until the current phase passes all acceptance criteria.
- **Test coverage ≥ 90% is required to close any phase.** This is enforced by the test runner — not self-assessed.
- **EXPLICIT OVER IMPLICIT. ALWAYS.**

---

## ⚠ DRY Rule — Read Before Every Phase

Before creating any model, table, column, or enum:

1. Run: `docker-compose exec db psql -U postgres -d kaihle -c '\dt'`
2. Run: `ls backend/app/models/`
3. Cross-check against the [Existing Models Reference](#existing-models-reference).

**If the table already exists → add columns via migration. Do NOT create a new file.**
**If this document and the codebase conflict → the codebase wins. Flag it before writing code.**

---

## Platform Overview

Kaihle is a multi-tenant SaaS platform. A **Super Admin** approves schools. A **School Admin** manages students and teachers. **Teachers** create classes. **Students** take diagnostic assessments and receive personalised multi-modal study plans. **Parents** have read-only visibility into their child's progress.

```
KaihleSystem (Super Admin)
  └── School  (school_code, status, plan_tier)
       ├── Admin(s)         SCHOOL_ADMIN role
       ├── Teacher(s)       TEACHER role
       ├── SchoolGrade(s)   school_id + grade_id (FK → grades)
       │    └── Student(s)  self-registered with school_code, approved + grade assigned
       └── SchoolClass      teacher creates for a grade + subject
            ├── ClassEnrollment      auto-enrolled students (engine only, never manual)
            ├── ClassTopic           teacher selects FROM existing topics table
            ├── ClassSubtopic        derived from ClassTopics → existing subtopics table
            └── ClassStudyPlanCourse thin bridge: class context ↔ student's StudyPlanCourse
                 └── StudyPlanCourse (EXISTING) — all progress, status, time_spent lives here
```

---

## Existing Models Reference

> These tables already exist. Do not recreate them. Extend via migration only.

| Table | Model Class | File | Key Columns |
|---|---|---|---|
| `student_profiles` | `StudentProfile` | `app/models/student_profile.py` | `id`, `user_id`, `grade_id` FK→`grades.id`, `curriculum_id`, `learning_profile` JSONB |
| `study_plans` | `StudyPlan` | `app/models/study_plan.py` | `id`, `student_id`, `assessment_id`, `subject_id`, `profile_fingerprint`, `status`, `total_weeks` |
| `study_plan_courses` | `StudyPlanCourse` | `app/models/study_plan.py` | `id`, `study_plan_id`, `course_id`, `topic_id`, `subtopic_id`, `week`, `day`, `sequence_order`, `activity_type`, `custom_content` JSONB, `status`, `time_spent_minutes`, `completed_at` |
| `grades` | `Grade` | `app/models/` | `id`, `label` (e.g. "Grade 8"), `level` (int 5–12). **Curriculum entity. Do not recreate.** |
| `courses` | `Course` | `app/models/` | `id`, `title`, `subject_id`, `topic_id`, `subtopic_id`, `grade_id`. **Curriculum entity.** |
| `topics` | `Topic` | `app/models/` | `id`, `subject_id`, `name`, `grade_id`. **Curriculum entity.** |
| `subtopics` | `Subtopic` | `app/models/` | `id`, `topic_id`, `name`. **Curriculum entity.** |
| `subjects` | `Subject` | `app/models/` | `id`, `name`, `curriculum_id` |
| `curricula` | `Curriculum` | `app/models/` | `id`, `name`, `code` |
| `assessments` | `Assessment` | `app/models/assessment.py` | `id`, `student_id`, `subject_id`, `status`, `created_at` |
| `assessment_reports` | `AssessmentReport` | `app/models/assessment.py` | `id`, `assessment_id`, `knowledge_gaps` JSONB, `strengths` JSONB, `mastery_scores` JSONB |

> **Critical:** `study_plan_courses` already has `status`, `time_spent_minutes`, `completed_at`, `sequence_order`. Do NOT add these to any new table — read them from `StudyPlanCourse` via a join.

---

## Build Sequence

```
─── PILOT GATE BUILD (build these first) ──────────────────────────
  Phase 1  · Auth + School Registration + Student School-Code Flow
  Phase 2  · School Admin Dashboard
  Phase 3  · Class Management + Auto-Enrollment Engine
  Phase 4  · Super Admin Dashboard
  Phase 5  · Teacher Dashboard (class-contextual)

  ★ PILOT MVP GATE — do not proceed until gate is cleared ★

─── POST-PILOT BUILD ───────────────────────────────────────────────
  Phase 6  · RAG Pipeline (pgvector + PDF ingestion + embeddings + query)
  Phase 7  · S3 Infrastructure + GeneratedContent Model
  Phase 8  · Enriched Study Plan Task (RAG + multi-modal LLM output)
  Phase 9  · Media Workers (Manim animation, infographic, practice questions)
  Phase 10 · Content Reuse Engine (profile fingerprinting + dedup)
  Phase 11 · Content Delivery API
  Phase 12 · Student Frontend (full diagnostic + study plan + media)

  ★ SEED RAISE (Month 6–9) ★

  Phase 13 · Parent Visibility Portal
```

---

## Environment Variables

All environment variables must be documented in `.env.example`. Never hardcode secrets.

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/kaihle

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Auth
JWT_SECRET_KEY=your_secret_key_min_32_chars_cryptographically_random
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# School
SCHOOL_REGISTRATION_APPROVAL_REQUIRED=true

# LLM — general (runpod | autocontentapi | google)
LLM_PROVIDER=runpod
LLM_MAX_TOKENS=4000
LLM_TEMPERATURE=0.3
LLM_TIMEOUT_SECONDS=90
RUNPOD_API_BASE=https://api.runpod.ai/v2/{endpoint_id}/openai/v1
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_MODEL=your_deployed_model_name
AUTOCONTENTAPI_BASE_URL=https://api.autocontentapi.com/v1
AUTOCONTENTAPI_KEY=your_autocontentapi_key
AUTOCONTENTAPI_MODEL=model_name

# LLM — Google Gemini (study plan + media generation only)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_LLM_MODEL=gemini-2.5-pro
GEMINI_FLASH_MODEL=gemini-2.5-flash
GEMINI_IMAGE_MODEL=imagen-3.0-generate-002
GEMINI_EMBEDDING_MODEL=text-embedding-004
GEMINI_TTS_VOICE=Kore

# S3 / MinIO
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=kaihle-content
S3_PRESIGNED_URL_TTL_SECONDS=3600
USE_MINIO=true
MINIO_ENDPOINT=http://minio:9000

# Study Plan
STUDY_PLAN_MIN_WEEKS=4
STUDY_PLAN_MAX_WEEKS=16

# RAG
EMBEDDING_DIMENSIONS=768
RAG_TOP_K=5
RAG_MIN_SIMILARITY=0.72
RAG_CHUNK_SIZE_TOKENS=400
RAG_CHUNK_OVERLAP_TOKENS=80

# Media generation
ANIMATION_MAX_DURATION_SECONDS=180
ANIMATION_MAX_SCENES=8
PRACTICE_QUESTIONS_PER_SUBTOPIC=10
MANIM_QUALITY_FLAG=-ql
MANIM_MAX_FIX_ATTEMPTS=5
```

---

## Test Coverage Requirements

Every phase must meet ≥ 90% coverage before the branch is closed.

**Backend:**
```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```

**Frontend:**
```bash
npm run test -- --coverage --coverageThreshold='{"global":{"lines":90}}'
```

Coverage below 90% blocks branch closure. Write missing tests before proceeding.

---
---

# PHASE 1 — Auth + School Registration + Student School-Code Flow

**Branch:** `feature/phase-1-auth-school-registration`
**Depends on:** Nothing (first phase)

## Goal

Implement the full multi-role authentication system. School admins self-register and await Super Admin approval. Students self-register using a `school_code`. No one can log in until their account is approved.

## New Files to Create

```
backend/app/models/school.py
backend/app/models/school_grade.py
backend/app/models/school_registration.py
backend/app/models/teacher.py               (already exist)
backend/app/api/v1/auth.py                  (modify existing or create)
backend/app/api/v1/schools.py               (new)
backend/app/core/security.py                (JWT logic)
backend/app/schemas/auth.py
backend/app/schemas/school.py
alembic/versions/001_add_schools.py
alembic/versions/002_add_school_grades.py
alembic/versions/003_add_student_school_registrations.py
alembic/versions/005_add_user_role.py
```

## Data Models

### School

```python
# app/models/school.py
class SchoolStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    ACTIVE           = "active"
    SUSPENDED        = "suspended"

class PlanTier(str, enum.Enum):
    TRIAL   = "trial"    # 30 students max
    STARTER = "starter"  # 100 students
    GROWTH  = "growth"   # 500 students
    SCALE   = "scale"    # unlimited

class School(Base):
    __tablename__ = 'schools'
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id     = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    name         = Column(String(255), nullable=False)
    slug         = Column(String(100), nullable=False, unique=True)
    school_code  = Column(String(8), unique=True, nullable=True)  # NULL until approved
    curriculum_id= Column(UUID(as_uuid=True), ForeignKey('curricula.id'), nullable=False)
    country      = Column(String(100), nullable=True)
    timezone     = Column(String(64), nullable=False, default='Asia/Makassar')
    status       = Column(SAEnum(SchoolStatus), nullable=False, default=SchoolStatus.PENDING_APPROVAL)
    plan_tier    = Column(SAEnum(PlanTier), nullable=False, default=PlanTier.TRIAL)
    approved_at  = Column(DateTime(timezone=True), nullable=True)
    approved_by  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (Index('idx_schools_status', 'status'),
                      Index('idx_schools_admin_id', 'admin_id'))
```

### SchoolGrade

> `grades` table already exists. This is a roster junction only. Do NOT create a new Grade model.

```python
# app/models/school_grade.py
class SchoolGrade(Base):
    __tablename__ = 'school_grades'
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id     = Column(UUID(as_uuid=True), ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    grade_id      = Column(UUID(as_uuid=True), ForeignKey('grades.id'), nullable=False)
    # ↑ References EXISTING grades table (Grade 5–12). Do NOT create a new grades table.
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint('school_id', 'grade_id'),
                      Index('idx_sg_school_id', 'school_id'))
```

### StudentSchoolRegistration

```python
# app/models/school_registration.py
class RegistrationStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class StudentSchoolRegistration(Base):
    __tablename__ = 'student_school_registrations'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id   = Column(UUID(as_uuid=True), ForeignKey('schools.id'), nullable=False)
    student_id  = Column(UUID(as_uuid=True), ForeignKey('student_profiles.id'), nullable=False)
    status      = Column(SAEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.PENDING)
    grade_id    = Column(UUID(as_uuid=True), ForeignKey('grades.id'), nullable=True)
    # ↑ Set on approval. References EXISTING grades.id — same FK as student_profiles.grade_id
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint('school_id', 'student_id'),
                      Index('idx_ssr_school_status', 'school_id', 'status'))
```

### Teacher


# app/models/teacher.py - exist


### User Role Enum (add to users table)

```python
class UserRole(str, enum.Enum):
    STUDENT       = "student"
    TEACHER       = "teacher"
    SCHOOL_ADMIN  = "school_admin"
    SUPER_ADMIN   = "super_admin"
```

Add `role` column to `users` table via migration `005_add_user_role.py`.

## school_code Generation

- Generated **only** on Super Admin approval. Never at self-registration.
- Format: 8 chars, uppercase alphanumeric. Exclude ambiguous chars: `0`, `O`, `1`, `I`, `L`.
- Algorithm: `uuid4()` → base36 encode → first 8 chars → uniqueness check against DB → retry on collision (max 10 attempts, then raise `RuntimeError`).

## API Endpoints

### Auth Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register/school-admin` | Create school admin + school (PENDING) |
| `POST` | `/api/v1/auth/register/student` | Create student + registration (PENDING) |
| `POST` | `/api/v1/auth/login` | Role-aware JWT login |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Current user profile with role + school_id |

**POST /api/v1/auth/register/school-admin — Request:**
```json
{
  "admin_name": "string",
  "admin_email": "string",
  "password": "string (min 8 chars)",
  "school_name": "string",
  "country": "string",
  "curriculum_id": "uuid"
}
```
Creates: `User` (role=SCHOOL_ADMIN) + `School` (status=PENDING_APPROVAL, school_code=NULL).
Sends: confirmation email "Your school is under review."
Returns: `201` with `{ user_id, school_id, status: "pending_approval" }`.

**POST /api/v1/auth/register/student — Request:**
```json
{
  "full_name": "string",
  "email": "string",
  "password": "string (min 8 chars)",
  "school_code": "string (8 chars)"
}
```
Validates: `school_code` → finds active School (status=ACTIVE). Returns `422` if code invalid, `403` if school is PENDING or SUSPENDED.
Creates: `User` (role=STUDENT) + `StudentProfile` + `StudentSchoolRegistration` (status=PENDING).
Sends: notification to school admin.
Returns: `201` with `{ user_id, school_name, status: "pending_approval" }`.

**POST /api/v1/auth/login — Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "role": "school_admin | student | teacher | super_admin",
  "school_id": "uuid | null"
}
```
JWT payload must include: `user_id`, `role`, `school_id` (null for super_admin).

### School Grade Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/schools/{school_id}/grades` | Add a curriculum grade to this school's roster |
| `GET` | `/api/v1/schools/{school_id}/grades` | List school's active grades |
| `DELETE` | `/api/v1/schools/{school_id}/grades/{grade_id}` | Remove grade (only if no students assigned) |

**POST /api/v1/schools/{school_id}/grades — Request:**
```json
{
  "grade_id": "uuid (must be a valid existing grades.id)"
}
```
Creates `SchoolGrade` junction row. Returns `409` if grade already exists for this school + year.

### Student Registration Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/schools/{school_id}/student-registrations` | List registrations (filterable by status) |
| `PATCH` | `/api/v1/schools/{school_id}/student-registrations/{reg_id}/approve` | Approve + assign grade |
| `PATCH` | `/api/v1/schools/{school_id}/student-registrations/{reg_id}/reject` | Reject with reason |

**PATCH .../approve — Request:**
```json
{
  "grade_id": "uuid (must be a grades.id that exists in school_grades for this school)"
}
```
On approve:
1. Set `StudentSchoolRegistration.status = APPROVED`
2. Set `StudentSchoolRegistration.grade_id = grade_id`
3. Set `StudentProfile.grade_id = grade_id`
4. Fire `AutoEnrollmentEngine.enroll_student_into_grade_classes()` (Phase 3)
5. Send confirmation email to student.

Returns `400` if `grade_id` not provided. Returns `404` if grade not in school's SchoolGrade roster.

## Redis Keys for Auth

```
kaihle:auth:refresh:{user_id}        TTL: 30 days  — refresh token hash
kaihle:auth:blacklist:{jti}          TTL: access token remaining lifetime
```

## Acceptance Criteria

- [ ] `POST /register/school-admin` creates School with `status=PENDING_APPROVAL` and `school_code=NULL`
- [ ] `POST /register/student` with invalid school_code returns `422` with clear message
- [ ] `POST /register/student` with PENDING school returns `403`
- [ ] `POST /register/student` with SUSPENDED school returns `403`
- [ ] JWT contains: `user_id`, `role`, `school_id`, expiry
- [ ] `GET /auth/me` returns correct role and school_id for each role type
- [ ] `PATCH .../approve` without `grade_id` returns `400`
- [ ] `PATCH .../approve` with grade_id not in school's SchoolGrade roster returns `404`
- [ ] `PATCH .../approve` sets `StudentProfile.grade_id` to existing `grades.id`
- [ ] `school_code` is exactly 8 chars, uppercase, no 0/O/1/I/L chars
- [ ] Duplicate `school_code` collision triggers retry (tested by mocking UUID to produce collision)
- [ ] No new `grades` table created — `school_grades.grade_id` references existing `grades.id`
- [ ] All migrations have working `downgrade()` methods
- [ ] All new Redis keys include explicit TTL
- [ ] Test coverage ≥ 90%

---
---

# PHASE 2 — School Admin Dashboard

**Branch:** `feature/phase-2-school-admin-dashboard`
**Depends on:** Phase 1

## Goal

Build the school admin backend endpoints and all frontend pages needed for the school admin to manage their school: approve students, manage grades, invite teachers, and view student progress.

## New Files to Create

```
backend/app/api/v1/school_admin.py
backend/app/schemas/school_admin.py
frontend/src/pages/admin/AdminDashboard.jsx
frontend/src/pages/admin/PendingRegistrations.jsx
frontend/src/pages/admin/ManageGrades.jsx
frontend/src/pages/admin/ManageTeachers.jsx
frontend/src/pages/admin/ManageStudents.jsx
frontend/src/pages/admin/StudentDetail.jsx
frontend/src/hooks/useSchoolAdmin.js
frontend/src/components/admin/GradeSelector.jsx
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/schools/{school_id}/dashboard` | SCHOOL_ADMIN | Stats summary |
| `POST` | `/api/v1/schools/{school_id}/teachers` | SCHOOL_ADMIN | Invite teacher by email |
| `GET` | `/api/v1/schools/{school_id}/teachers` | SCHOOL_ADMIN | List all teachers |
| `DELETE` | `/api/v1/schools/{school_id}/teachers/{teacher_id}` | SCHOOL_ADMIN | Deactivate teacher |
| `GET` | `/api/v1/schools/{school_id}/students` | SCHOOL_ADMIN | List all approved students |
| `PATCH` | `/api/v1/schools/{school_id}/students/{student_id}/grade` | SCHOOL_ADMIN | Reassign student grade |

**GET /dashboard — Response:**
```json
{
  "student_count": 0,
  "pending_registrations": 0,
  "teacher_count": 0,
  "class_count": 0,
  "avg_assessment_pct": 0.0
}
```

**POST /teachers — Request:**
```json
{
  "name": "string",
  "email": "string"
}
```
Creates: `User` (role=TEACHER, temp password) + `Teacher` row. Sends invite email with login link and forced password change flag.
Returns `409` if email already registered.

**PATCH /students/{id}/grade — Request:**
```json
{
  "grade_id": "uuid (existing grades.id in school's SchoolGrade roster)"
}
```
Updates `StudentProfile.grade_id`. Triggers re-enrollment via `AutoEnrollmentEngine` (Phase 3).

## Frontend Pages

All admin pages are mobile-responsive at ≥ 768px.

| Page | Route | Key Elements | States |
|---|---|---|---|
| Admin Dashboard | `/admin/dashboard` | Stats cards, pending badge (red if >0), quick-action buttons | Loading skeleton, empty school |
| Pending Registrations | `/admin/registrations` | Table: name, email, date. Per row: Grade dropdown + Approve + Reject | No pending, no grades yet (CTA to add grade first) |
| Manage Grades | `/admin/grades` | SchoolGrade list with student counts. Add form selects from curriculum grades | First grade prompt |
| Manage Teachers | `/admin/teachers` | Table: name, email, class count, status. Invite form | Email already in use error |
| Manage Students | `/admin/students` | Searchable table: name, grade, assessment status. Filter by grade | Empty, no results |
| Student Detail | `/admin/students/:id` | Per-subject diagnostic status, classes enrolled, grade | Assessment not started |

### Grade Dropdown

The grade dropdown in the Pending Registrations page is populated by:
```
GET /api/v1/schools/{school_id}/grades
→ Returns SchoolGrade rows joined to Grade.label
→ Display: "Grade 8", "Grade 9", etc.
→ Value: grades.id (not school_grades.id)
```

Show inline validation error "Please select a grade" if admin clicks Approve without selecting a grade.

## Acceptance Criteria

- [ ] `GET /dashboard` counts match DB exactly (no approximations)
- [ ] `POST /teachers` with existing email returns `409`
- [ ] `PATCH /students/{id}/grade` with grade not in school's roster returns `404`
- [ ] SCHOOL_ADMIN cannot access another school's endpoints — returns `403`
- [ ] Grade dropdown populated from `SchoolGrade` joined to `Grade.label` — not a raw grades query
- [ ] Approving without selecting grade shows inline error — no API call made
- [ ] Grade cannot be deleted while students are assigned — returns `409`
- [ ] All admin pages render correctly on 768px viewport
- [ ] Test coverage ≥ 90%

---
---

# PHASE 3 — Class Management + Auto-Enrollment Engine

**Branch:** `feature/phase-3-class-enrollment`
**Depends on:** Phase 1, Phase 2

## Goal

Teachers create classes for a grade + subject. Students in that grade are automatically enrolled. A thin bridge table (`ClassStudyPlanCourse`) links class context to student personalised content. All progress data lives on the existing `StudyPlanCourse` — not on any new table.

## New Files to Create

```
backend/app/models/school_class.py
backend/app/models/class_enrollment.py
backend/app/models/class_topic.py                  (ClassTopic + ClassSubtopic)
backend/app/models/class_study_plan_course.py
backend/app/services/enrollment/auto_enrollment.py
backend/app/api/v1/classes.py
backend/app/schemas/classes.py
alembic/versions/006_add_school_classes.py
alembic/versions/007_add_class_enrollments.py
alembic/versions/008_add_class_topics_subtopics.py
alembic/versions/009_add_class_study_plan_courses.py
```

## Data Models

### SchoolClass

```python
# app/models/school_class.py
class SchoolClass(Base):
    __tablename__ = 'school_classes'
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id     = Column(UUID(as_uuid=True), ForeignKey('schools.id'), nullable=False)
    teacher_id    = Column(UUID(as_uuid=True), ForeignKey('teachers.id'), nullable=False)
    grade_id      = Column(UUID(as_uuid=True), ForeignKey('grades.id'), nullable=False)
    # ↑ References EXISTING grades.id
    subject_id    = Column(UUID(as_uuid=True), ForeignKey('subjects.id'), nullable=False)
    # ↑ References EXISTING subjects.id
    name          = Column(String(100), nullable=False)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index('idx_sc_school_grade', 'school_id', 'grade_id'),
                      Index('idx_sc_teacher', 'teacher_id'))
```

### ClassEnrollment

```python
# app/models/class_enrollment.py
# Auto-populated by AutoEnrollmentEngine ONLY. Never via any API endpoint.
class ClassEnrollment(Base):
    __tablename__ = 'class_enrollments'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id    = Column(UUID(as_uuid=True), ForeignKey('school_classes.id', ondelete='CASCADE'), nullable=False)
    student_id  = Column(UUID(as_uuid=True), ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active   = Column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('class_id', 'student_id'),
                      Index('idx_ce_class_id', 'class_id'),
                      Index('idx_ce_student_id', 'student_id'))
```

### ClassTopic + ClassSubtopic

> `topics` and `subtopics` tables already exist. These are teacher-curated selection junctions, NOT new entities.

```python
# app/models/class_topic.py
class ClassTopic(Base):
    __tablename__ = 'class_topics'
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id       = Column(UUID(as_uuid=True), ForeignKey('school_classes.id', ondelete='CASCADE'), nullable=False)
    topic_id       = Column(UUID(as_uuid=True), ForeignKey('topics.id'), nullable=False)
    # ↑ References EXISTING topics.id — teacher selects which topics to cover
    sequence_order = Column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('class_id', 'topic_id'),
                      Index('idx_ct_class_id', 'class_id'))

class ClassSubtopic(Base):
    __tablename__ = 'class_subtopics'
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id       = Column(UUID(as_uuid=True), ForeignKey('school_classes.id', ondelete='CASCADE'), nullable=False)
    class_topic_id = Column(UUID(as_uuid=True), ForeignKey('class_topics.id', ondelete='CASCADE'), nullable=False)
    subtopic_id    = Column(UUID(as_uuid=True), ForeignKey('subtopics.id'), nullable=False)
    # ↑ References EXISTING subtopics.id — auto-derived from teacher's ClassTopic selection
    sequence_order = Column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('class_id', 'subtopic_id'),
                      Index('idx_cst_class_id', 'class_id'))
```

### ClassStudyPlanCourse

> **Do NOT add progress fields here.** `study_plan_courses` already has `status`, `time_spent_minutes`, `completed_at`. Read those via a join.

```python
# app/models/class_study_plan_course.py
class ClassStudyPlanCourse(Base):
    __tablename__ = 'class_study_plan_courses'
    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id             = Column(UUID(as_uuid=True), ForeignKey('school_classes.id', ondelete='CASCADE'), nullable=False)
    student_id           = Column(UUID(as_uuid=True), ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False)
    class_subtopic_id    = Column(UUID(as_uuid=True), ForeignKey('class_subtopics.id', ondelete='CASCADE'), nullable=False)
    study_plan_course_id = Column(UUID(as_uuid=True), ForeignKey('study_plan_courses.id', ondelete='SET NULL'), nullable=True)
    # NULL until student completes diagnostic and StudyPlanCourse is generated (Phase 8).
    # Set by AutoEnrollmentEngine.link_to_study_plan_course() after Phase 8 writes rows.
    # To read progress: JOIN to study_plan_courses on this FK. Do not duplicate those fields here.
    created_at           = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint('class_id', 'student_id', 'class_subtopic_id'),
                      Index('idx_cspc_class_id', 'class_id'),
                      Index('idx_cspc_student_id', 'student_id'),
                      Index('idx_cspc_spc_id', 'study_plan_course_id'))
```

## Auto-Enrollment Engine

**File:** `app/services/enrollment/auto_enrollment.py`

All methods are synchronous. No Celery tasks. No LLM calls. All operations are idempotent.

```python
class AutoEnrollmentEngine:

    def enroll_student_into_grade_classes(
        self, student_id: UUID, grade_id: UUID, school_id: UUID, db: Session
    ) -> dict:
        """
        Called when: student registration is approved and grade_id is set.
        1. Find all active SchoolClasses where class.grade_id = grade_id AND class.school_id = school_id.
        2. For each class: INSERT ClassEnrollment (student_id, class_id). Ignore on conflict.
        3. For each class: call _create_class_study_plan_courses(student_id, class_id, db).
        Returns: { "enrolled_classes": N }
        """

    def enroll_grade_students_into_class(
        self, class_id: UUID, school_id: UUID, grade_id: UUID, db: Session
    ) -> dict:
        """
        Called when: new SchoolClass is created.
        1. Find all StudentSchoolRegistrations where school_id = school_id AND grade_id = grade_id AND status = APPROVED.
        2. For each student: INSERT ClassEnrollment. Ignore on conflict.
        3. For each student: call _create_class_study_plan_courses(student_id, class_id, db).
        Returns: { "enrolled_students": N }
        """

    def _create_class_study_plan_courses(
        self, student_id: UUID, class_id: UUID, db: Session
    ) -> None:
        """
        For each ClassSubtopic in the class:
          INSERT ClassStudyPlanCourse(class_id, student_id, class_subtopic_id, study_plan_course_id=NULL).
          Ignore on conflict (UniqueConstraint).
          If student already has a StudyPlanCourse for this subtopic_id — link it immediately.
        """

    def link_to_study_plan_course(
        self, student_id: UUID, subtopic_id: UUID, study_plan_course_id: UUID, db: Session
    ) -> int:
        """
        Called by: generate_enriched_study_plan task (Phase 8) after StudyPlanCourse rows are written.
        Updates ClassStudyPlanCourse.study_plan_course_id for all rows where:
          class_subtopic.subtopic_id = subtopic_id AND student_id = student_id.
        Returns: number of rows updated.
        """
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/schools/{school_id}/classes` | TEACHER | Create class, fires enrollment engine |
| `GET` | `/api/v1/schools/{school_id}/classes` | TEACHER / SCHOOL_ADMIN | List classes |
| `GET` | `/api/v1/classes/{class_id}` | TEACHER | Class detail |
| `POST` | `/api/v1/classes/{class_id}/topics` | TEACHER | Assign topic list (replaces existing) |
| `GET` | `/api/v1/classes/{class_id}/students` | TEACHER | Students + progress via StudyPlanCourse join |

**POST /schools/{school_id}/classes — Request:**
```json
{
  "grade_id": "uuid (existing grades.id in school's SchoolGrade roster)",
  "subject_id": "uuid (existing subjects.id)",
  "name": "Grade 8 Mathematics A",
}
```
1. Creates `SchoolClass`.
2. Calls `AutoEnrollmentEngine.enroll_grade_students_into_class()`.
3. Returns `{ "class_id": "uuid", "enrolled_students": N }`.

**POST /classes/{class_id}/topics — Request:**
```json
{
  "topic_ids": ["uuid", "uuid", "..."]
}
```
1. Replaces all existing `ClassTopic` rows for this class (delete old, insert new).
2. Derives `ClassSubtopic` rows from each topic's subtopics.
3. Creates new `ClassStudyPlanCourse` rows for any new subtopics (for all enrolled students).
4. Does NOT delete existing `ClassStudyPlanCourse` rows for removed topics.

**GET /classes/{class_id}/students — Response:**
```json
{
  "students": [
    {
      "student_id": "uuid",
      "name": "string",
      "diagnostic_status": "not_started | in_progress | completed",
      "plans_linked": 3,
      "plans_total": 8,
      "avg_progress_pct": 45
    }
  ]
}
```
Query: `ClassStudyPlanCourse LEFT JOIN study_plan_courses`. `study_plan_course_id IS NULL` → not started.

## Acceptance Criteria

- [ ] `ClassStudyPlanCourse` table has exactly 6 columns: `id`, `class_id`, `student_id`, `class_subtopic_id`, `study_plan_course_id`, `created_at`. No others.
- [ ] `ClassStudyPlanCourse` has no `status`, `progress_percentage`, `mastery_level`, or `time_spent` columns
- [ ] Creating a class with 10 students in the grade creates exactly 10 `ClassEnrollment` rows
- [ ] Running `enroll_student_into_grade_classes` twice for the same student produces 0 duplicate rows (idempotent)
- [ ] `POST /classes/{id}/topics` with 3 topics creates `ClassSubtopic` rows for all their subtopics
- [ ] `GET /classes/{id}/students` joins to `StudyPlanCourse` — progress comes from that table, not new fields
- [ ] `link_to_study_plan_course` correctly sets `study_plan_course_id` and returns correct row count
- [ ] Teacher can only access their own classes — `403` for other teachers' classes
- [ ] `school_classes.grade_id` references existing `grades.id` — verified via psql `\d school_classes`
- [ ] All migrations have working `downgrade()` methods
- [ ] Test coverage ≥ 90%

---
---

# PHASE 4 — Super Admin Dashboard

**Branch:** `feature/phase-4-super-admin-dashboard`
**Can run parallel with Phase 2 and Phase 3**

## Goal

Super Admin can see all schools, approve or reject school registrations, manage plan tiers, view usage analytics, and impersonate school admins for support.

## New Files to Create

```
backend/app/models/usage_event.py
backend/app/models/audit_log.py
backend/app/api/v1/super_admin.py
backend/app/schemas/super_admin.py
frontend/src/pages/superadmin/SuperAdminDashboard.jsx
frontend/src/pages/superadmin/SchoolList.jsx
frontend/src/pages/superadmin/ApprovalQueue.jsx
frontend/src/pages/superadmin/SchoolDetail.jsx
frontend/src/pages/superadmin/PlatformAnalytics.jsx
alembic/versions/010_add_usage_events.py
alembic/versions/011_add_audit_logs.py
```

## Data Models

```python
# app/models/usage_event.py
class UsageEvent(Base):
    __tablename__ = 'usage_events'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id   = Column(UUID(as_uuid=True), ForeignKey('schools.id'), nullable=False)
    event_type  = Column(String(50), nullable=False)
    # Valid event_type values:
    # 'diagnostic_completed', 'study_plan_generated', 'animation_generated',
    # 'infographic_generated', 'student_enrolled', 'admin_impersonated'
    student_id  = Column(UUID(as_uuid=True), nullable=True)
    metadata    = Column(JSONB, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index('idx_ue_school_id', 'school_id'),
                      Index('idx_ue_recorded_at', 'recorded_at'))

# app/models/audit_log.py
class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    impersonated_by   = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    school_id         = Column(UUID(as_uuid=True), ForeignKey('schools.id'), nullable=False)
    action            = Column(String(100), nullable=False)
    recorded_at       = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index('idx_al_school_id', 'school_id'),)
```

## API Endpoints

All endpoints require `SUPER_ADMIN` role. Return `403` for any other role.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/superadmin/schools` | List schools, paginated, filterable by status |
| `GET` | `/api/v1/superadmin/schools/{school_id}` | School detail + stats |
| `POST` | `/api/v1/superadmin/schools/{school_id}/approve` | Approve school, generate school_code, send email |
| `POST` | `/api/v1/superadmin/schools/{school_id}/reject` | Reject with reason |
| `POST` | `/api/v1/superadmin/schools/{school_id}/suspend` | Suspend school |
| `POST` | `/api/v1/superadmin/schools/{school_id}/reactivate` | Reactivate suspended school |
| `PATCH` | `/api/v1/superadmin/schools/{school_id}/plan-tier` | Change plan tier |
| `GET` | `/api/v1/superadmin/schools/{school_id}/usage` | Monthly usage_events aggregated |
| `GET` | `/api/v1/superadmin/analytics` | Platform-wide totals |
| `POST` | `/api/v1/superadmin/impersonate/{school_id}` | Create impersonation JWT (15-min TTL) |

**POST .../approve:** Sets `School.status = ACTIVE`, generates `school_code` (see Phase 1 generation rules), sends email to school admin. Records `UsageEvent(event_type='admin_impersonated')`.

**POST .../impersonate/{school_id}:**
- Issues a new JWT with 15-minute TTL.
- JWT payload: `{ user_id, role: "school_admin", school_id, is_impersonation: true, impersonated_by: <super_admin_user_id> }`.
- Logs to `AuditLog`: `impersonated_by`, `school_id`, `action="impersonation_started"`.
- Impersonation sessions **cannot**: change `plan_tier`, delete school, create super admin users. Return `403` for any of these actions.

**Plan Tier Limits:**

| Tier | Student Limit |
|---|---|
| `trial` | 30 |
| `starter` | 100 |
| `growth` | 500 |
| `scale` | Unlimited |

Enforce limit on `PATCH .../student-registrations/{id}/approve` — check current student count against plan tier before approving. Return `403` with `{ "error": "plan_limit_reached", "limit": N }` if exceeded.

## Frontend Pages

| Page | Route | Key Elements | States |
|---|---|---|---|
| Super Admin Dashboard | `/superadmin/dashboard` | Platform stats, pending count badge (amber >0) | Loading, no schools |
| School List | `/superadmin/schools` | Searchable table. Filter tabs: All / Pending / Active / Suspended | Empty per filter |
| Approval Queue | `/superadmin/schools?status=pending_approval` | School info per row + Approve + Reject (reason required) | Empty queue |
| School Detail | `/superadmin/schools/:id` | Stats, 6-month usage chart, Impersonate button, Suspend / Reactivate | Suspended (red border) |
| Platform Analytics | `/superadmin/analytics` | Charts: signups, enrollments, assessments, content per month. Toggle: 30 / 90 / all days | No data, loading skeleton |

## Acceptance Criteria

- [ ] `POST .../approve` sets `status=ACTIVE` and generates unique `school_code`
- [ ] `POST .../approve` sends email to school admin with `school_code`
- [ ] `POST .../impersonate` JWT has `is_impersonation=true` and 15-minute TTL
- [ ] Impersonation session logged to `audit_logs`
- [ ] Impersonation session returns `403` on `PATCH plan-tier` attempt
- [ ] `GET /superadmin/schools` returns `403` for SCHOOL_ADMIN or TEACHER roles
- [ ] Approving a student when school is at plan tier limit returns `403` with `plan_limit_reached`
- [ ] All migrations have working `downgrade()` methods
- [ ] Test coverage ≥ 90%

---
---

# PHASE 5 — Teacher Dashboard (Class-Contextual)

**Branch:** `feature/phase-5-teacher-dashboard`
**Depends on:** Phase 3

## Goal

Teachers see their classes, manage the class syllabus (selecting from the existing curriculum topics), and view per-student progress. Progress data is read from `StudyPlanCourse` via the `ClassStudyPlanCourse` bridge — no separate progress model.

## New Files to Create

```
backend/app/api/v1/teacher.py
backend/app/schemas/teacher.py
frontend/src/pages/teacher/MyClasses.jsx
frontend/src/pages/teacher/ClassDashboard.jsx
frontend/src/pages/teacher/SyllabusManager.jsx
frontend/src/pages/teacher/ClassStudentList.jsx
frontend/src/pages/teacher/StudentProgress.jsx
frontend/src/components/teacher/CreateClassDrawer.jsx
frontend/src/components/teacher/MasteryRing.jsx
```

## API Endpoints

All endpoints require `TEACHER` role. Teachers can only access classes where `school_classes.teacher_id = their teacher record id`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/teacher/classes` | List teacher's classes with stats |
| `GET` | `/api/v1/teacher/classes/{class_id}` | Class detail: student count, topic count, avg mastery |
| `GET` | `/api/v1/teacher/classes/{class_id}/students` | Students + progress summary from StudyPlanCourse |
| `GET` | `/api/v1/teacher/classes/{class_id}/students/{student_id}/progress` | Per-subtopic progress for one student |

**GET /teacher/classes/{class_id}/students/{student_id}/progress — Response:**
```json
{
  "student_id": "uuid",
  "class_id": "uuid",
  "subtopics": [
    {
      "class_subtopic_id": "uuid",
      "subtopic_name": "string",
      "study_plan_course_id": "uuid | null",
      "status": "not_started | in_progress | completed | null",
      "time_spent_minutes": 0,
      "completed_at": "ISO8601 | null"
    }
  ]
}
```

Query pattern:
```sql
SELECT cspc.class_subtopic_id, sub.name AS subtopic_name,
       cspc.study_plan_course_id,
       spc.status, spc.time_spent_minutes, spc.completed_at
FROM class_study_plan_courses cspc
JOIN class_subtopics cs ON cs.id = cspc.class_subtopic_id
JOIN subtopics sub ON sub.id = cs.subtopic_id
LEFT JOIN study_plan_courses spc ON spc.id = cspc.study_plan_course_id
WHERE cspc.class_id = :class_id AND cspc.student_id = :student_id
```

`study_plan_course_id IS NULL` → student has not completed diagnostic. Return `status: null`, `time_spent_minutes: 0`.

## Frontend Pages

All pages mobile-responsive at ≥ 768px.

| Page | Key Elements | States |
|---|---|---|
| My Classes | Class cards: subject icon, grade badge, name, student count, syllabus %. "Create Class" button | No classes (empty state with CTA) |
| Create Class Drawer | Grade dropdown (from SchoolGrade), Subject dropdown, Name field, preview: "N students will be auto-enrolled" | No grades, no subjects |
| Class Dashboard | Stats cards: enrolled, topics, active plans, avg mastery. Tabs: Students / Syllabus | No syllabus, no students |
| Syllabus Tab | Two-column: available topics (from existing topics table) on left, selected + reorderable on right | Unsaved changes warning on navigate |
| Students Tab | Table: name, diagnostic status badge, plans linked / total, avg progress % from StudyPlanCourse | All not started |
| Student Progress | Per-subtopic list: name, mastery ring, status badge, progress % from StudyPlanCourse | Awaiting assessment (gray state) |

## Acceptance Criteria

- [ ] Teacher returns `403` for classes they do not own
- [ ] Student progress data comes from `StudyPlanCourse` via `ClassStudyPlanCourse` join — no separate progress fields queried
- [ ] `study_plan_course_id IS NULL` renders "Awaiting assessment" in UI — no crash or empty error
- [ ] Create Class drawer shows accurate auto-enrollment count before submission (calculated from existing registrations)
- [ ] Syllabus Manager topic list populated from existing `topics` table filtered by subject
- [ ] `sequence_order` persisted correctly after reordering topics
- [ ] All pages render correctly at 768px
- [ ] Test coverage ≥ 90%

---
---

## ★ PILOT MVP GATE ★

> Do NOT begin Phase 6 until ALL of the following are confirmed:
>
> 1. Phases 1–5 deployed and accessible from a real browser (not localhost)
> 2. A school has been approved via Super Admin — `school_code` working end-to-end
> 3. At least one teacher has created a class and can see student progress
> 4. At least 1 Bali micro-school founder has received a live demo and provided feedback
>
> **Business target:** signed pilot agreement within 90 days.
> **Exception:** Phase 6 (PDF extraction only — no infra, no LLM) may begin once Cambridge PDFs are available.

---
---

# PHASE 6 — RAG Pipeline

**Branch:** `feature/phase-6-rag-pipeline`
**Depends on:** Pilot Gate cleared

## Goal

Ingest Cambridge curriculum PDF textbooks into PostgreSQL with pgvector. Build the embedding pipeline and query service that will power personalised study plan generation.

## Sub-phases (build in order)

### 6A — pgvector Schema

**Branch:** `feature/phase-6a-rag-schema`

Docker image: switch to `pgvector/pgvector:pg16` in `docker-compose.yml`.

```python
# app/models/rag.py
class CurriculumContent(Base):
    __tablename__ = 'curriculum_content'
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subtopic_id    = Column(UUID(as_uuid=True), ForeignKey('subtopics.id'), nullable=False)
    topic_id       = Column(UUID(as_uuid=True), ForeignKey('topics.id'), nullable=False)
    subject_id     = Column(UUID(as_uuid=True), ForeignKey('subjects.id'), nullable=False)
    grade_id       = Column(UUID(as_uuid=True), ForeignKey('grades.id'), nullable=False)
    # ↑ All 4 FKs reference EXISTING tables
    content_text   = Column(Text, nullable=False)
    content_source = Column(String(255), nullable=False)  # e.g. "cambridge_grade8_math_ch3.pdf"
    chunk_index    = Column(Integer, nullable=False)
    created_at     = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index('idx_cc_subtopic_id', 'subtopic_id'),)

class CurriculumEmbedding(Base):
    __tablename__ = 'curriculum_embeddings'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id  = Column(UUID(as_uuid=True), ForeignKey('curriculum_content.id', ondelete='CASCADE'), nullable=False)
    subtopic_id = Column(UUID(as_uuid=True), ForeignKey('subtopics.id'), nullable=False)
    embedding   = Column(Vector(768), nullable=False)  # text-embedding-004 output
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

IVFFlat index (created in migration, not in SQLAlchemy model):
```sql
CREATE INDEX idx_ce_embedding_ivfflat
ON curriculum_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### 6B — PDF Extraction + Ingestion

**Branch:** `feature/phase-6b-rag-pdf-extraction`

- PDF source: `backend/data/textbooks/`
- Naming convention: `{grade_code}_{subject_code}_{type}.pdf` e.g. `grade8_math_textbook.pdf`
- Cambridge only until Month 6. Do not accept other curricula.
- Use `PyMuPDF` for extraction, `tiktoken` for chunk size measurement.
- Chunk size: `RAG_CHUNK_SIZE_TOKENS` (default 400). Overlap: `RAG_CHUNK_OVERLAP_TOKENS` (default 80).

### 6C — Embedding Ingestion (Celery Task)

**Branch:** `feature/phase-6c-rag-embedding-ingestion`

- Task name: `tasks.ingest_curriculum_embeddings`
- Queue: `default`
- Uses Gemini `text-embedding-004` (768 dimensions) via `google.generativeai` SDK directly (sanctioned Gemini bypass — see AGENTS.md Section 3.1).
- Rate limit: `rate_limit="30/m"` on the Celery task.
- On rate limit error: retry with exponential backoff.

### 6D — Query Service

**Branch:** `feature/phase-6d-rag-query-service`

```python
# app/services/rag/query_service.py
class RAGQueryService:
    def retrieve_for_subtopic(self, subtopic_id: UUID, query_text: str) -> list[ContentChunk]:
        """
        1. Embed query_text via EmbeddingService (text-embedding-004).
        2. Cosine similarity query with IVFFlat index.
        3. Filter results below RAG_MIN_SIMILARITY threshold.
        4. Return list[ContentChunk] sorted by similarity descending.
        5. If zero results: log WARNING, return [] — do NOT raise.
        """
```

## Acceptance Criteria (all sub-phases)

- [ ] `pgvector/pgvector:pg16` Docker image used — verified by `SELECT * FROM pg_extension WHERE extname='vector'`
- [ ] `IVFFlat` index created — verified via `EXPLAIN ANALYZE` on similarity query
- [ ] `retrieve_for_subtopic` returns empty list (not exception) when no chunks found
- [ ] Chunks with similarity < `RAG_MIN_SIMILARITY` excluded from results
- [ ] Rate limit on embedding task triggers exponential backoff retry — not immediate failure
- [ ] `CurriculumContent.grade_id` and `subtopic_id` FK to EXISTING tables — verified via psql
- [ ] Test coverage ≥ 90%

---
---

# PHASE 7 — S3 Infrastructure + GeneratedContent Model

**Branch:** `feature/phase-7-s3-infrastructure`
**Depends on:** Phase 6

## Goal

Wire AWS S3 (production) and MinIO (development) into the platform. Build the `GeneratedContent` model that tracks every media asset generated for a student. All S3 uploads happen in Celery workers only — never in the API layer.

## New Files to Create

```
backend/app/services/storage/s3_client.py
backend/app/services/storage/content_metadata_service.py
backend/app/services/storage/key_generator.py
backend/app/models/generated_content.py
alembic/versions/012_add_generated_content.py
```

## Data Model

```python
# app/models/generated_content.py
class ContentType(str, enum.Enum):
    ANIMATION           = "animation"
    INFOGRAPHIC         = "infographic"
    PRACTICE_QUESTIONS  = "practice_questions"

class GenerationStatus(str, enum.Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    REUSED    = "reused"

class GeneratedContent(Base):
    __tablename__ = 'generated_content'
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id          = Column(UUID(as_uuid=True), ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False)
    study_plan_id       = Column(UUID(as_uuid=True), ForeignKey('study_plans.id', ondelete='CASCADE'), nullable=False)
    subtopic_id         = Column(UUID(as_uuid=True), ForeignKey('subtopics.id', ondelete='CASCADE'), nullable=False)
    content_type        = Column(SAEnum(ContentType), nullable=False)
    status              = Column(SAEnum(GenerationStatus), nullable=False, default=GenerationStatus.PENDING)
    s3_key              = Column(String(500), nullable=True)
    s3_bucket           = Column(String(100), nullable=True)
    file_size_bytes     = Column(Integer, nullable=True)
    profile_fingerprint = Column(String(64), nullable=False)
    prompt_hash         = Column(String(64), nullable=False)
    llm_provider        = Column(String(50), nullable=True)
    media_provider      = Column(String(50), nullable=True)
    error_message       = Column(Text, nullable=True)
    reused_from_id      = Column(UUID(as_uuid=True), ForeignKey('generated_content.id', ondelete='SET NULL'), nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at        = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index('idx_gc_student_subtopic_type', 'student_id', 'subtopic_id', 'content_type'),
        Index('idx_gc_fingerprint_type_subtopic', 'profile_fingerprint', 'content_type', 'subtopic_id'),
        Index('idx_gc_prompt_hash_type', 'prompt_hash', 'content_type'),
        Index('idx_gc_study_plan_id', 'study_plan_id'),
    )
```

## S3 Key Format

```
{content_type}/{grade_code}/{subject_code}/{subtopic_id}/{prompt_hash}.{ext}

Examples:
  animation/grade8/math/550e8400.../a3f9c1d2.mp4
  infographic/grade8/math/550e8400.../a3f9c1d2.png
  practice_questions/grade8/math/550e8400.../a3f9c1d2.json
  specs/grade8/math/550e8400.../a3f9c1d2_spec.json
```

`prompt_hash` = SHA-256 of `json.dumps(prompt_inputs, sort_keys=True, ensure_ascii=True)`.

Required keys in `prompt_inputs`:
`grade_code`, `subject_code`, `subtopic_id`, `mastery_band`, `priority`, `rag_content_ids` (sorted list), `learning_style`, `content_type`.

Missing any key must raise `KeyError` immediately (Fail Fast — AGENTS.md Section 10).

## Acceptance Criteria

- [ ] MinIO container starts and passes healthcheck in dev compose
- [ ] `upload_bytes` and `upload_json` raise exception when called from a FastAPI route — architectural test
- [ ] `generate_presigned_url` is the only S3 operation callable from the API layer
- [ ] `download_json` raises `S3Client.NotFoundError` for non-existent key
- [ ] `GeneratedContent` PENDING → COMPLETED lifecycle round-trips correctly
- [ ] `mark_completed` raises `ValueError` if status is not PENDING
- [ ] `build_prompt_hash` raises `KeyError` if any required key is missing
- [ ] Same prompt inputs always produce the same hash (determinism test)
- [ ] Test coverage ≥ 90%

---
---

# PHASE 8 — Enriched Study Plan Task

**Branch:** `feature/phase-8-study-plan-task`
**Depends on:** Phase 6, Phase 7

## Goal

After a student completes a diagnostic assessment for a subject, generate a personalised multi-modal study plan using RAG context and Gemini 2.5 Pro. Write the plan to DB and dispatch media generation tasks.

**Important:** This task must call `AutoEnrollmentEngine.link_to_study_plan_course()` after writing `StudyPlanCourse` rows, so teachers can see content progress in the class dashboard.

## Sub-phases (build in order)

### 8A — StudyPlan Migration

**Branch:** `feature/phase-8a-studyplan-migration`

Add to existing `study_plans` table via migration:
- `subject_id UUID FK → subjects.id` (nullable initially, backfill, then not-null)
- `profile_fingerprint VARCHAR(64)`

Purge any existing test `StudyPlan` rows before adding constraints.

### 8B — Trigger Redesign (Per-Subject Chain)

**Branch:** `feature/phase-8b-trigger-redesign`

Deprecate old `tasks.generate_study_plan`. Replace with per-subject Celery chain:

```python
# Fired when student answers final question for Subject X:
chain(
    generate_assessment_report.s(assessment_id),
    generate_enriched_study_plan.s(assessment_id, subject_id)
).apply_async()
```

Redis guard to prevent duplicate chains:
```
kaihle:diagnostic:generating:{student_id}:{subject_id}   TTL: 7200s
Values: "generating" | "study_plan" | "media_generation" | "complete" | "failed"
```

### 8C — RAG Prompt Injection

**Branch:** `feature/phase-8c-rag-prompt-injection`

Task: `tasks.generate_enriched_study_plan`
Queue: `study_plans`
LLM: Gemini 2.5 Pro via `google.generativeai` SDK directly (sanctioned bypass — AGENTS.md 3.1).

Before calling LLM, check S3-backed cache (AGENTS.md Section 3.4.1):
1. Build `prompt_hash` from all inputs.
2. Query `generated_content WHERE prompt_hash = :hash AND content_type = :type AND status = 'completed'`.
3. If found → return existing `s3_key`. Do not call LLM.

### 8D — Multi-Modal LLM Output + Validation

**Branch:** `feature/phase-8d-multimodal-llm-schema`

LLM returns JSON containing `animation_spec`, `infographic_spec`, `practice_questions` per subtopic.

Validation rules (fail fast — reject entire response on any violation):
- `difficulty` must be Integer 1–5. No floats, no strings. (AGENTS.md Section 2)
- `correct_answer` must exactly match one of `options`.
- `week` ≥ 1 and ≤ `total_weeks`.
- `day` ≥ 1 and ≤ 5.
- Minimum 10 practice questions per subtopic.
- All `subtopic_id` values must match the IDs provided in the prompt (do not invent).

On `JSONDecodeError`: retry (max 3). On validation failure: retry (max 3). On exhaustion: write `StudyPlan(status="generation_failed")`.

### 8E — DB Write + S3 + Dispatch + Link

**Branch:** `feature/phase-8e-persist-and-dispatch`

Full pipeline:
1. Upload raw spec JSON to S3 (`specs/...` key).
2. Write `StudyPlan` + `StudyPlanCourse` rows (one per gap subtopic) in a single transaction.
   - `StudyPlanCourse.activity_type = "ai_content"`
   - `StudyPlanCourse.custom_content` = `{ animation_spec, infographic_spec, practice_questions, spec_s3_key }`
3. **Call `AutoEnrollmentEngine.link_to_study_plan_course(student_id, subtopic_id, study_plan_course_id, db)` for each `StudyPlanCourse` row written.** This is required for teachers to see progress in class views.
4. Create `GeneratedContent` PENDING rows (3 per subtopic: animation, infographic, practice_questions).
5. Call `reuse_or_dispatch()` per content item (Phase 10 implements reuse; Phase 8 dispatches directly).
6. Update Redis flag to `"media_generation"` on success, `"failed"` on exhaustion.

## Acceptance Criteria

- [ ] Exactly 1 `StudyPlan` row created per task invocation
- [ ] Exactly 1 `StudyPlanCourse` row per validated gap subtopic
- [ ] `StudyPlanCourse.activity_type` is always `"ai_content"` for these rows
- [ ] `link_to_study_plan_course` called for every `StudyPlanCourse` row written
- [ ] S3-backed cache checked before LLM call — duplicate prompt_hash returns existing s3_key without LLM call
- [ ] `difficulty` values in practice questions are all Integer 1–5 — no floats or strings pass validation
- [ ] All DB writes in a single transaction — no partial study plan possible
- [ ] `StudyPlan(status="generation_failed")` written on exhaustion — no `StudyPlanCourse` rows in that case
- [ ] Redis flag updated correctly on success and failure
- [ ] Test coverage ≥ 90%

---
---

# PHASE 9 — Media Workers

**Branch:** See sub-phases below
**Depends on:** Phase 7, Phase 8

## Goal

Generate three media content types per gap subtopic: Manim animation (MP4), infographic (PNG via Imagen 3), practice questions (JSON). All tasks are Celery workers. Animation runs in `manim_worker` on `manim_queue`. Others run in `celery_worker` on `default` queue.

## Sub-phases

### 9A — Manim Worker Container

**Branch:** `feature/phase-9a-manim-worker`

- Create `backend/Dockerfile.manim` — installs Manim 0.19.0, LaTeX, FFmpeg, Cairo, manim-voiceover.
- `celery_worker` container must NOT have Manim installed — verify in CI.
- Task `tasks.generate_animation_manim` routes to `manim_queue` **only**. Any routing to `default` is a hard violation (AGENTS.md Section 1 Rule 10).
- `--concurrency=2` for Manim worker (CPU-bound Cairo rendering).

### 9B — Animation + Voiceover Task

**Branch:** `feature/phase-9b-animation-task`

Task: `tasks.generate_animation_manim`
Queue: `manim_queue` (manim_worker only)
Time limit: 600 seconds
Max retries: 3

6-stage pipeline:
1. Download spec JSON from S3.
2. Scene planner LLM call (Gemini 2.5 Pro).
3. Manim code generator LLM call (Gemini Flash).
4. Execute + fix loop (max `MANIM_MAX_FIX_ATTEMPTS` attempts, Gemini Flash for fixes).
5. Gemini TTS voiceover via `manim-voiceover`.
6. Render + upload MP4 to S3. Mark `GeneratedContent` COMPLETED.

### 9C — Practice Questions Task

**Branch:** `feature/phase-9c-practice-questions`

Task: `tasks.generate_practice_questions`
Queue: `default`
No LLM call — questions already validated in Phase 8D.

1. Download spec JSON from S3.
2. Extract `practice_questions` array.
3. Re-validate: clamp `difficulty` to Integer 1–5, skip questions with empty `question_text` or mismatched `correct_answer`.
4. If < 5 valid questions remain: mark `GeneratedContent` FAILED.
5. Upload final JSON to S3. Mark COMPLETED.

### 9D — Infographic Task

**Branch:** `feature/phase-9d-infographic`

Task: `tasks.generate_infographic`
Queue: `default`

1. Download spec JSON from S3.
2. Build Gemini Imagen 3 prompt from `infographic_spec`.
3. Call Imagen 3 API (`imagen-3.0-generate-002`). On safety filter rejection: mark FAILED immediately — do not retry (deterministic rejection).
4. Upload PNG to S3. Mark COMPLETED.

## Acceptance Criteria

- [ ] `tasks.generate_animation_manim` only registered in `manim_queue` — verified by inspecting task routing config
- [ ] `celery_worker` container does not have Manim importable — verified by attempting `import manim` in that container
- [ ] Practice questions task clamps `difficulty` to Integer 1–5 — float input produces integer output
- [ ] Practice questions task marks FAILED when < 5 valid questions remain after re-validation
- [ ] Imagen 3 safety filter rejection marks FAILED immediately (no retry)
- [ ] Each task logs: started, completed, failed with structured JSON (AGENTS.md Section 9)
- [ ] All S3 upload operations are inside worker tasks only — no API layer uploads
- [ ] Test coverage ≥ 90%

---
---

# PHASE 10 — Content Reuse Engine

**Branch:** `feature/phase-10-content-reuse`
**Depends on:** Phase 7, Phase 8

## Goal

Avoid regenerating identical media content. Two students whose learning profiles map to the same `profile_fingerprint` share S3 assets for the same subtopic.

## New Files to Create

```
backend/app/services/storage/profile_fingerprint.py
backend/app/services/storage/content_reuse_service.py
```

## Profile Fingerprint

```python
# app/services/storage/profile_fingerprint.py
MASTERY_BANDS = [(0.40, "beginning"), (0.60, "developing"), (0.75, "approaching")]

def mastery_band(mastery_level: float) -> str:
    for threshold, band in MASTERY_BANDS:
        if mastery_level < threshold:
            return band
    return "strong"

def build_profile_fingerprint(
    grade_code: str, curriculum_id: str, subject_code: str,
    gap_subtopics: list[dict],  # [{"subtopic_id": str, "mastery_level": float}]
    learning_style: str | None,
) -> str:
    """
    Returns 64-char hex SHA-256.
    gap_subtopics sorted by subtopic_id before hashing (order must not matter).
    learning_style None → "general".
    mastery_level discretised into band (0.28 and 0.35 both map to "beginning" → same fingerprint).
    """
```

## Reuse Logic

```python
# app/services/storage/content_reuse_service.py
class ContentReuseService:
    def reuse_or_dispatch(
        self,
        new_content_id: UUID,
        profile_fingerprint: str,
        subtopic_id: UUID,
        content_type: ContentType,
        spec_s3_key: str,
        dispatch_task_fn: Callable,
    ) -> bool:
        """
        1. Query generated_content WHERE profile_fingerprint = :fp AND subtopic_id = :sid
           AND content_type = :type AND status = 'completed'.
        2. If found → mark_reused(new_content_id, found.id, found.s3_key). Return True.
        3. If not found → dispatch_task_fn(str(new_content_id), spec_s3_key). Return False.
        Uses idx_gc_fingerprint_type_subtopic index.
        """
```

Plug `ContentReuseService.reuse_or_dispatch()` into Phase 8E's dispatch step.

## Acceptance Criteria

- [ ] `mastery_band(0.39)` → `"beginning"`, `mastery_band(0.40)` → `"developing"` (boundary)
- [ ] Same `gap_subtopics` in different order → same fingerprint (sort test)
- [ ] `learning_style=None` and `learning_style="general"` → same fingerprint
- [ ] Student A generates animation for subtopic X. Student B with same fingerprint → animation REUSED, task NOT dispatched
- [ ] Student A and B with different fingerprints → both dispatch independently
- [ ] `reuse_or_dispatch` uses `idx_gc_fingerprint_type_subtopic` index — verified via EXPLAIN
- [ ] Test coverage ≥ 90%

---
---

# PHASE 11 — Content Delivery API

**Branch:** `feature/phase-11-content-api`
**Depends on:** Phase 7

## Goal

Expose endpoints for the student frontend to poll generation status and retrieve presigned S3 URLs for completed content.

## New Endpoints

Add to `app/api/v1/routers/diagnostic.py`:

| Method | Path | Description |
|---|---|---|
| `GET` | `/diagnostic/{student_id}/study-plans` | All study plans for student (one per completed subject) |
| `GET` | `/diagnostic/{student_id}/study-plans/{study_plan_id}/content` | All content + presigned URLs for one plan |
| `GET` | `/diagnostic/{student_id}/study-plans/{study_plan_id}/content/{subtopic_id}` | Content for one subtopic |

**Auth rules (enforced at service layer — not just route):**
- If `current_user.role == STUDENT`: `student_id` must equal `current_user.student_profile.id`.
- If `current_user.role == PARENT` (Phase 13): `student_id` must be a registered child.
- Any other case: raise `403`.

**Presigned URL rules:**
- `generate_presigned_url` is the only S3 operation permitted in the API layer.
- For PENDING rows: `url = null`, `url_expires_at = null`.
- For FAILED rows: `url = null`, `url_expires_at = null`.
- For COMPLETED / REUSED rows: generate presigned URL with `S3_PRESIGNED_URL_TTL_SECONDS`.

Frontend polls this endpoint every 8 seconds while `generation_status != "complete"`. Partial results (some COMPLETED, some PENDING) are returned without blocking.

## Acceptance Criteria

- [ ] `GET .../content` returns presigned URLs for COMPLETED rows and `null` for PENDING rows
- [ ] Student accessing another student's content returns `403`
- [ ] Polling with mix of COMPLETED and PENDING subtopics returns partial results (not blocked)
- [ ] `generate_presigned_url` is the only boto3 call in the API layer — verified by grep
- [ ] Test coverage ≥ 90%

---
---

# PHASE 12 — Student Frontend

**Branch:** `feature/phase-12-student-frontend`
**Depends on:** Phases 1–5, Phase 11

## Goal

Full student-facing React application: registration, diagnostic flow, report, study plan, and multi-modal content viewer.

## Pages

| Page | Route | Key Elements | States |
|---|---|---|---|
| Registration | `/register` | Email, full name, password, school_code. School name shown after valid code entered. | Invalid code, inactive school, duplicate email |
| Pending Approval | `/pending` | "Your registration is under review by [School Name]." Logout only. | Static informational |
| Login | `/login` | Email + password. Role-aware redirect after login. | Wrong credentials, locked account |
| Diagnostic Hub | `/diagnostic` | 4 subject cards: status badge + progress. Study plan badge when complete. | Not started / in progress / complete per subject |
| Diagnostic Session | `/diagnostic/:subject` | Progress bar, question + 4 options, submit. Option locks on click. No back button. | Loading, submitting, session complete |
| Diagnostic Report | `/diagnostic/:subject/report` | Polls `/content` every 8s. MasteryRing per topic. KnowledgeGapBadge per subtopic. | Generating (skeleton), partial, loaded |
| Study Plan View | `/study-plan/:subject` | Week accordion, subtopic list per week, content status badges | Generating, partial, loaded |
| Content View | `/study-plan/:subject/:subtopic` | AnimationPlayer, InfographicViewer, PracticeQuestionsPanel | PENDING (skeleton), COMPLETED, FAILED |

**No `localStorage` or `sessionStorage` usage anywhere.** All state in React hooks or in-memory.

## Acceptance Criteria

- [ ] `school_code` input fetches school name on blur — shows school name or error inline
- [ ] Diagnostic session has no back button — answered question cannot be re-answered
- [ ] Diagnostic Report polls every 8 seconds — stops polling when all content is COMPLETED
- [ ] AnimationPlayer does not render until `study_plan_course_id` is linked (not null)
- [ ] PracticeQuestionsPanel difficulty rendered as label (Beginner / Easy / Medium / Hard / Expert) — not raw integer (AGENTS.md Section 2)
- [ ] No `localStorage` or `sessionStorage` usage — verified by grep
- [ ] All pages mobile-responsive at ≥ 375px
- [ ] Test coverage ≥ 90%

---
---

# PHASE 13 — Parent Visibility Portal

**Branch:** `feature/phase-13-parent-portal`
**Depends on:** Phase 12, seed raise

## Goal

Parents can register, be linked to their child(ren) by the school admin, and view a read-only version of each child's diagnostic report and study plan.

## New Files to Create

```
backend/app/models/parent_profile.py   (ParentProfile + ParentStudent)
backend/app/api/v1/parent.py
alembic/versions/013_add_parent_profiles.py
frontend/src/pages/parent/ParentHome.jsx
frontend/src/pages/parent/ChildReport.jsx
frontend/src/pages/parent/ChildStudyPlan.jsx
```

## Data Models

```python
class ParentProfile(Base):
    __tablename__ = 'parent_profiles'
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class ParentStudent(Base):
    __tablename__ = 'parent_students'
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id  = Column(UUID(as_uuid=True), ForeignKey('parent_profiles.id'), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey('student_profiles.id'), nullable=False)
    linked_by  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)  # school admin
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint('parent_id', 'student_id'),)
```

Parent-student linking is done by school admin only. Parents cannot link themselves.

## Acceptance Criteria

- [ ] Parent can only access data for their own registered children — `403` for others (enforced at service layer)
- [ ] Parent views are read-only — no action buttons, no form submissions
- [ ] `POST /auth/register/parent` creates User (role=PARENT) + ParentProfile
- [ ] Parent cannot link themselves to a student — only SCHOOL_ADMIN can create ParentStudent rows
- [ ] All pages mobile-responsive at ≥ 375px
- [ ] Test coverage ≥ 90%

---

## Open Decisions

| Decision | Required Before | Notes |
|---|---|---|
| Cambridge PDFs sourced and named correctly | Phase 6B | `{grade_code}_{subject_code}_{type}.pdf`. Cambridge only until Month 6. |
| IB curriculum gate | Month 6 review | Add only if a pilot school is on IB. `curriculum_id` already parameterised — no platform rebuild. |
| Gemini API key provisioned (LLM + TTS + Imagen 3) | Phase 8C | One key covers all three services. Confirm all capabilities enabled on project. |
| AWS S3 bucket region | Phase 7 | Bali → `ap-southeast-1` recommended. Set `AWS_REGION` in `.env`. |
| RunPod pod specs for manim_worker | Phase 9A | CPU pod. Pod size determines `--concurrency`. Start with 2. |
| manim-voiceover Gemini TTS adapter | Phase 9B | Custom `AbstractSpeechService` subclass needed. `GTTSService` as fallback. |
| JWT_SECRET_KEY | Phase 1 | Min 32 chars, cryptographically random. Use AWS Secrets Manager in prod. |
| Email provider | Phase 1 | Transactional email for: school approval, student registration, teacher invite. Recommend Resend or Postmark. |
| Pilot school seed data (names + admin emails) | Phase 5 demo | Required to seed School + Teacher + SchoolGrade in staging for Bali founder demo. |
| Plan tier limits enforcement — hard or soft cap | Phase 4 | TRIAL=30, STARTER=100, GROWTH=500, SCALE=unlimited. Recommend hard reject with clear error. |

---

*Kaihle MVP Roadmap v1.0 · February 2026 · CONFIDENTIAL*
