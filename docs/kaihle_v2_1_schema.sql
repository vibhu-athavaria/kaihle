-- =============================================================================
-- Kaihle v2.2 — Canonical Database Schema
-- =============================================================================
-- Prepared by: Kramer (Technical Lead)
-- Updated:     2026-05-15
-- Supersedes:  Kaihle v2.1 schema
-- Strategy:    Migrate — new schema, data imported via scripts
--
-- Design principles:
--   1. Curriculum layer is completely school-agnostic
--   2. subtopic is the atomic unit of knowledge — all gap tracking anchors here
--   3. assessments are class-level definitions; student_attempts are per-student
--   4. Billing is per-school, not per-student
--   5. subject/grade/curriculum always derived from subtopic via joins — no duplication
--   6. pgvector embedding lives on subtopics — RAG context at the right granularity
-- =============================================================================

-- ---------------------------------------------------------------------------
-- EXTENSIONS
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- trigram search on question_text
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector for subtopic embeddings

-- ---------------------------------------------------------------------------
-- ENUMS
-- ---------------------------------------------------------------------------

CREATE TYPE assessment_type AS ENUM (
    'DIAGNOSTIC',      -- broad, finds knowledge gaps, start of term
    'TOPIC_SPECIFIC',  -- focused on one curriculum_topic, after teaching
    'PROGRESS_CHECK',  -- short pulse check mid-topic, 5-8 questions
    'FINAL'            -- end of term/year, comprehensive
);

CREATE TYPE assessment_status AS ENUM (
    'DRAFT',           -- teacher building, not visible to students
    'ACTIVE',          -- students can start attempts
    'CLOSED'           -- no new attempts, results visible
);

CREATE TYPE attempt_status AS ENUM (
    'NOT_STARTED',
    'IN_PROGRESS',
    'COMPLETED',
    'ABANDONED'
);

CREATE TYPE question_type AS ENUM (
    'MCQ',             -- multiple choice — scored by rule only
    'TRUE_FALSE',      -- scored by rule only
    'SHORT_ANSWER'     -- scored by LLM async
);

CREATE TYPE scored_by AS ENUM (
    'RULE',            -- exact match, immediate
    'LLM',             -- AI-scored, stored with justification
    'PENDING'          -- queued for async LLM scoring
);

CREATE TYPE study_plan_status AS ENUM (
    'GENERATING',      -- Celery task running
    'ACTIVE',          -- student can access
    'COMPLETED',       -- student finished all resources + quiz
    'ABANDONED'
);

CREATE TYPE resource_type AS ENUM (
    'VIDEO',
    'ARTICLE',
    'INTERACTIVE'
);

CREATE TYPE lesson_plan_status AS ENUM (
    'GENERATING',      -- Celery task running (v2.2: added GENERATING state)
    'GENERATED',
    'EDITED',          -- teacher modified it
    'USED',            -- teacher delivered it
    'ARCHIVED'
);

-- v2.2: failure codes for lesson plan generation errors
CREATE TYPE lesson_plan_failure_code AS ENUM (
    'llm_auth_error',
    'llm_rate_limit_error',
    'llm_connection_error',
    'llm_unexpected_error',
    'json_parse_failed',
    'class_not_found'
);

CREATE TYPE subscription_tier AS ENUM (
    'TRIAL',           -- 15 days, max 30 students
    'STARTER',         -- max 100 students, 1 curriculum
    'GROWTH',          -- max 500 students, 2 curricula
    'SCALE'            -- unlimited students, 3+ curricula
);

CREATE TYPE subscription_status AS ENUM (
    'ACTIVE',
    'PAST_DUE',
    'CANCELLED',
    'EXPIRED'
);

CREATE TYPE payment_status AS ENUM (
    'PENDING',
    'PAID',
    'FAILED',
    'REFUNDED'
);

CREATE TYPE user_role AS ENUM (
    'STUDENT',
    'TEACHER',
    'SCHOOL_ADMIN',
    'PARENT',
    'KAIHLE_ADMIN'
);

CREATE TYPE auth_token_type AS ENUM (
    'MAGIC_LINK',
    'REFRESH',
    'PASSWORD_RESET'   -- v2.2: added for password reset flow
);

CREATE TYPE onboarding_status AS ENUM (
    'PENDING',       -- student enrolled but has not started onboarding
    'IN_PROGRESS',   -- at least one Tier 1 diagnostic created; not all completed
    'COMPLETED'      -- all Tier 1 diagnostics completed AND learning profile submitted
);

-- v2.2: enum types for subtopic_content (replacing VARCHAR columns)
CREATE TYPE content_type AS ENUM (
    'video',
    'explanation',
    'practice',
    'quiz'
);

CREATE TYPE review_status AS ENUM (
    'pending',
    'approved',
    'rejected'
);

-- =============================================================================
-- SECTION 1: CURRICULUM LAYER
-- Completely school-agnostic. No school_id on any of these tables.
-- Seeded once by Kaihle Admin. Schools consume them, never own them.
-- Hierarchy: curricula → curriculum_subjects → curriculum_topics → subtopics
-- =============================================================================

CREATE TABLE curricula (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    code        VARCHAR(50)  NOT NULL,  -- e.g. 'cambridge_lower', 'igcse', 'ib_myp'
    description TEXT,
    country     VARCHAR(100),           -- NULL for international boards like IB
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    CONSTRAINT curricula_code_key UNIQUE (code),
    CONSTRAINT curricula_name_key UNIQUE (name)
);

COMMENT ON TABLE curricula IS
    'Global curriculum boards. School-agnostic.
     e.g. Cambridge Lower Secondary (code=cambridge_lower),
          IGCSE (code=igcse), IB MYP (code=ib_myp).
     Schools adopt curricula via school_curricula junction table.';

-- ---------------------------------------------------------------------------

CREATE TABLE subjects (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(100) NOT NULL,
    code                VARCHAR(20)  NOT NULL,  -- e.g. 'MATH', 'SCI', 'ENG'
    description         TEXT,
    icon                VARCHAR(50),            -- icon identifier for UI
    color               VARCHAR(7),             -- hex color e.g. '#0D9488'
    subject_family_code VARCHAR(20),            -- v2.2: groups related subjects e.g. 'SCIENCE'
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    CONSTRAINT subjects_code_key UNIQUE (code),
    CONSTRAINT subjects_name_key UNIQUE (name)
);

COMMENT ON TABLE subjects IS
    'Global subject catalogue. School-agnostic.
     e.g. Mathematics (MATH), Science (SCI), English Language (ENG).
     Used directly by classes and question_bank joins.
     subject_family_code (v2.2): groups related subjects e.g. BIO/CHEM/PHY under SCIENCE.';

CREATE INDEX idx_subjects_family_code ON subjects (subject_family_code);

-- ---------------------------------------------------------------------------

CREATE TABLE grades (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(50)  NOT NULL,  -- e.g. 'Grade 7', 'Year 9'
    level       INT          NOT NULL,  -- numeric for ordering: 6, 7, 8, ..., 12
    description TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    CONSTRAINT grades_level_key   UNIQUE (level),
    CONSTRAINT grades_level_range CHECK (level BETWEEN 1 AND 13)
);

COMMENT ON TABLE grades IS
    'Global grade levels. School-agnostic.
     level is numeric for range queries (grade.level BETWEEN 6 AND 9).';

-- ---------------------------------------------------------------------------

CREATE TABLE topics (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL,
    canonical_code  VARCHAR(50),        -- e.g. 'MATH-ALG' — reused across grades
    description     TEXT,
    keywords        TEXT[],
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

COMMENT ON TABLE topics IS
    'Topics are school-agnostic AND grade-agnostic.
     "Algebra" exists once as a topic. It appears in Grade 7 and Grade 9
     via separate curriculum_topics rows. Subtopics differ per grade.
     This is the key insight: topics are stable across grades, subtopics vary.';

CREATE INDEX idx_topics_canonical_code ON topics (canonical_code);

-- ---------------------------------------------------------------------------
-- curriculum_subjects: declares which subjects belong to a curriculum.
-- e.g. IGCSE offers Mathematics, Science, English, History, etc.
-- ---------------------------------------------------------------------------

CREATE TABLE curriculum_subjects (
    curriculum_id   UUID    NOT NULL REFERENCES curricula (id) ON DELETE CASCADE,
    subject_id      UUID    NOT NULL REFERENCES subjects (id)  ON DELETE CASCADE,
    is_core         BOOLEAN NOT NULL DEFAULT TRUE,  -- FALSE for elective subjects
    sort_order      INT,
    PRIMARY KEY (curriculum_id, subject_id)
);

COMMENT ON TABLE curriculum_subjects IS
    'Which subjects belong to a curriculum.
     is_core=FALSE marks elective subjects.
     Used to validate that a class curriculum+subject combination is valid.';

-- ---------------------------------------------------------------------------
-- curriculum_grades: declares which grades belong to a curriculum.
-- Mirrors curriculum_subjects pattern.
-- Allows admin to declare grade coverage before any topics are added.
-- ---------------------------------------------------------------------------

CREATE TABLE curriculum_grades (
    curriculum_id   UUID    NOT NULL REFERENCES curricula (id) ON DELETE CASCADE,
    grade_id        UUID    NOT NULL REFERENCES grades (id)    ON DELETE CASCADE,
    sort_order      INT,
    PRIMARY KEY (curriculum_id, grade_id)
);

CREATE INDEX idx_curriculum_grades_grade_id ON curriculum_grades (grade_id);

COMMENT ON TABLE curriculum_grades IS
    'Which grades belong to a curriculum.
     Mirrors curriculum_subjects pattern.
     Allows admin to declare grade coverage before topics are added.
     e.g. Cambridge Lower Secondary covers Grades 6, 7, 8.';

-- ---------------------------------------------------------------------------
-- curriculum_topics: THE pivot table.
-- Binds curriculum + subject + grade + topic into one teachable unit.
-- This is your proposed design and it is correct.
-- "Algebra taught in Grade 7 under Cambridge" is one row.
-- "Algebra taught in Grade 9 under Cambridge" is a different row.
-- "Algebra taught in Grade 9 under IB" is yet another row.
-- Subtopics hang off this via curriculum_topic_id — they differ per row.
-- ---------------------------------------------------------------------------

CREATE TABLE curriculum_topics (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id       UUID        NOT NULL REFERENCES curricula (id)  ON DELETE CASCADE,
    subject_id          UUID        NOT NULL REFERENCES subjects (id)   ON DELETE CASCADE,
    grade_id            UUID        NOT NULL REFERENCES grades (id)     ON DELETE CASCADE,
    topic_id            UUID        NOT NULL REFERENCES topics (id)     ON DELETE CASCADE,
    standard_code       VARCHAR(100),           -- official code e.g. '8Ma1'
    sequence_order      INT,                    -- teaching sequence within grade+subject
    learning_objectives TEXT[],                 -- official LOs for this placement
    recommended_weeks   INT,
    is_required         BOOLEAN     NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    CONSTRAINT curriculum_topics_unique
        UNIQUE (curriculum_id, subject_id, grade_id, topic_id),
    CONSTRAINT chk_ct_sequence CHECK (sequence_order IS NULL OR sequence_order > 0)
);

COMMENT ON TABLE curriculum_topics IS
    'The pivot table binding curriculum + subject + grade + topic.
     This is the level at which teaching is planned (Teacher Copilot focuses here).
     Subtopics hang off this via FK — subtopics CHANGE per grade even for the same topic.
     e.g. Cambridge IGCSE → Mathematics → Grade 9 → Algebra
          has different subtopics than Cambridge Lower → Mathematics → Grade 7 → Algebra.';

CREATE INDEX idx_ct_curriculum_subject_grade ON curriculum_topics (curriculum_id, subject_id, grade_id);
CREATE INDEX idx_ct_topic ON curriculum_topics (topic_id);

-- ---------------------------------------------------------------------------
-- subtopics: THE atomic unit of knowledge in Kaihle.
-- Every gap detection, every question, every study plan anchors here.
-- Belongs to exactly one curriculum_topic (which encodes curriculum+subject+grade+topic).
-- ---------------------------------------------------------------------------

CREATE TABLE subtopics (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_topic_id     UUID        NOT NULL
                                REFERENCES curriculum_topics (id) ON DELETE CASCADE,
    name                    TEXT        NOT NULL,
    canonical_code          VARCHAR(50),        -- e.g. '8Ma1.2' (standard_code.sequence)
    description             TEXT,
    learning_objective      TEXT        NOT NULL,
    -- Single clear LO — this is what gets embedded and sent to LLM in prompts.
    keywords                TEXT[],
    bloom_taxonomy_level    VARCHAR(50),        -- Remember|Understand|Apply|Analyse|Evaluate|Create
    difficulty_level        INT,
    estimated_minutes       INT,
    sequence_order          INT,
    is_active               BOOLEAN     NOT NULL DEFAULT TRUE,
    -- RAG EMBEDDING: embed(name + ' ' + learning_objective + ' ' + description)
    -- Populated by /scripts/ingest_curriculum.py
    -- Used for: study plan generation, Teacher Copilot RAG, content alignment scoring
    embedding               VECTOR(768),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,
    CONSTRAINT chk_subtopic_difficulty CHECK (difficulty_level IS NULL OR difficulty_level BETWEEN 1 AND 5)
);

COMMENT ON TABLE subtopics IS
    'Atomic unit of knowledge. Single FK to curriculum_topic (which carries full context).
     embedding: 768-dim vector from Google text-embedding-004.
     Embed: name + learning_objective + description concatenated.
     This embedding is the core RAG signal for all AI features:
       - content_curator.py: cosine_sim(resource_embed, subtopic.embedding) > 0.72
       - quiz_generator.py:  subtopic.embedding used to retrieve relevant chunks
       - Teacher Copilot:    subtopic.embedding in lesson plan prompt context
     Gap tracking (gap_states) references subtopic_id as primary FK.';

CREATE INDEX idx_subtopics_curriculum_topic ON subtopics (curriculum_topic_id);
CREATE INDEX idx_subtopics_canonical_code   ON subtopics (canonical_code);
-- Enable after data load with: CREATE INDEX idx_subtopics_embedding
--   ON subtopics USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ---------------------------------------------------------------------------
-- subtopic_prerequisites: prerequisite graph at atomic level.
-- This is what drives prerequisite-aware gap surfacing in the Gap Map.
-- Cross-grade prerequisites are valid and common.
-- ---------------------------------------------------------------------------

CREATE TABLE subtopic_prerequisites (
    subtopic_id             UUID NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    prerequisite_subtopic_id UUID NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    importance              VARCHAR(20) NOT NULL DEFAULT 'REQUIRED',
    -- REQUIRED: must master before attempting | RECOMMENDED | HELPFUL
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (subtopic_id, prerequisite_subtopic_id),
    CONSTRAINT chk_no_self_prereq CHECK (subtopic_id <> prerequisite_subtopic_id),
    CONSTRAINT chk_importance CHECK (importance IN ('REQUIRED', 'RECOMMENDED', 'HELPFUL'))
);

COMMENT ON TABLE subtopic_prerequisites IS
    'Prerequisite graph at subtopic level.
     Used by gap_service to surface upstream gaps first:
     if student has gap in B, and B requires A, show A gap before B.
     Cross-grade is valid: Grade 8 subtopic can require a Grade 7 subtopic.
     Seeded from curriculum JSON authored by Vibhu.';

-- ---------------------------------------------------------------------------
-- curriculum_chunks: PDF-sourced text for richer LLM context.
-- Optional for pilot (subtopic.embedding covers M1).
-- Added in M2 by /scripts/ingest_curriculum.py.
-- ---------------------------------------------------------------------------

CREATE TABLE curriculum_chunks (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    subtopic_id UUID        NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    content     TEXT        NOT NULL,
    chunk_index INT         NOT NULL,
    token_count INT,
    source_file VARCHAR(255),
    page_number INT,
    embedding   VECTOR(768),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,                    -- v2.2: added
    CONSTRAINT chk_chunk_index CHECK (chunk_index >= 0)
);

COMMENT ON TABLE curriculum_chunks IS
    'Text chunks extracted from Cambridge PDF files, linked to subtopics.
     500 tokens per chunk, 50 token overlap.
     Used for richer LLM context when generating quizzes and lesson plans.
     NOT required for pilot — subtopic.embedding is sufficient for M1.
     Populated by /scripts/ingest_curriculum.py in M2.';

CREATE INDEX idx_chunks_subtopic ON curriculum_chunks (subtopic_id);
-- Enable after load: CREATE INDEX idx_chunks_embedding
--   ON curriculum_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =============================================================================
-- SECTION 2: QUESTION BANK
-- subtopic_id is the ONLY curriculum FK.
-- subject / grade / curriculum / topic all derived via:
--   question_bank → subtopics → curriculum_topics → (subject, grade, curriculum, topic)
-- =============================================================================

CREATE TABLE question_bank (
    id                      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    subtopic_id             UUID    NOT NULL
                                REFERENCES subtopics (id) ON DELETE RESTRICT,
    question_text           TEXT    NOT NULL,
    question_type           question_type NOT NULL,
    options                 JSONB,
    -- MCQ format: [{"key": "A", "text": "..."}, {"key": "B", "text": "..."}, ...]
    -- NULL for TRUE_FALSE and SHORT_ANSWER
    correct_answer          TEXT    NOT NULL,
    -- MCQ: "A" | TRUE_FALSE: "true"/"false" | SHORT_ANSWER: model answer text
    explanation             TEXT,               -- shown after attempt submitted
    hints                   JSONB,              -- [{"order": 1, "text": "..."}, ...]
    difficulty_level        FLOAT,
    bloom_taxonomy_level    VARCHAR(50),
    estimated_time_seconds  INT,
    learning_objectives     TEXT[],
    canonical_form          TEXT    NOT NULL,   -- normalised for dedup
    problem_signature       JSONB   NOT NULL,   -- structural fingerprint
    source                  VARCHAR(10) NOT NULL DEFAULT 'bank',
    -- 'bank' = from founders 7K import | 'llm' = AI-generated at runtime
    meta_tags               JSONB,
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,
    CONSTRAINT chk_qb_difficulty CHECK (difficulty_level IS NULL OR difficulty_level BETWEEN 1.0 AND 5.0),
    CONSTRAINT chk_qb_source     CHECK (source IN ('bank', 'llm'))
);

COMMENT ON TABLE question_bank IS
    'Single canonical question store.
     subtopic_id is the ONLY curriculum FK — no redundant subject/grade/topic columns.
     All context derived via join: subtopics → curriculum_topics.
     source=bank: /scripts/import_questions.py maps existing 7K questions to subtopic_id.
     source=llm:  quiz_generator.py saves generated questions here for reuse.
     canonical_form + problem_signature: used to detect near-duplicate questions.';

CREATE INDEX idx_qb_subtopic   ON question_bank (subtopic_id);
CREATE INDEX idx_qb_type       ON question_bank (question_type);
CREATE INDEX idx_qb_difficulty ON question_bank (difficulty_level);
CREATE INDEX idx_qb_active     ON question_bank (is_active);
CREATE INDEX idx_qb_source     ON question_bank (source);
CREATE INDEX idx_qb_text_trgm  ON question_bank USING GIN (question_text gin_trgm_ops);

-- =============================================================================
-- SECTION 3: SCHOOL & USER MANAGEMENT
-- =============================================================================

CREATE TABLE schools (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    slug            VARCHAR(100) NOT NULL,  -- URL-safe unique ID, e.g. 'lighthouse-bali'
    address         VARCHAR(500),
    city            VARCHAR(100),
    country         VARCHAR(100),
    timezone        VARCHAR(50)  NOT NULL DEFAULT 'Asia/Singapore',
    -- Used for: lesson plan Monday 06:00 local, parent report Sunday 18:00 local
    contact_email   VARCHAR(255),
    contact_phone   VARCHAR(50),
    website         VARCHAR(255),
    logo_url        VARCHAR(500),
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    -- pending | active | suspended
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT schools_slug_key UNIQUE (slug),
    CONSTRAINT chk_school_status CHECK (status IN ('pending', 'active', 'suspended'))
);

COMMENT ON TABLE schools IS
    'One row per tenant. This is the multi-tenancy anchor.
     slug: used in API paths (/api/v1/schools/{slug}/...).
     status=pending: created, awaiting Kaihle Admin approval.
     timezone: critical for Celery beat scheduling of weekly AI jobs.';

CREATE INDEX idx_schools_status ON schools (status);

-- ---------------------------------------------------------------------------
-- school_curricula: which curricula a school has adopted.
-- Answers Q1 — multi-curriculum support.
-- ---------------------------------------------------------------------------

CREATE TABLE school_curricula (
    school_id       UUID    NOT NULL REFERENCES schools (id)   ON DELETE CASCADE,
    curriculum_id   UUID    NOT NULL REFERENCES curricula (id) ON DELETE RESTRICT,
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    adopted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (school_id, curriculum_id)
);

COMMENT ON TABLE school_curricula IS
    'Which curricula a school offers. Answers Q1 (multi-curriculum per school).
     LightHouse Bali running Cambridge + IB:
       (school_id, cambridge_id, is_primary=TRUE)
       (school_id, ib_id,        is_primary=FALSE)
     Service layer enforces: class.curriculum_id must exist in school_curricula.
     Tier limits enforced: STARTER can only have 1 curriculum (max_curricula=1).';

-- Enforce at most one primary curriculum per school
CREATE UNIQUE INDEX idx_school_curricula_one_primary
    ON school_curricula (school_id)
    WHERE is_primary = TRUE;

-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id           UUID        REFERENCES schools (id) ON DELETE SET NULL,
    -- NULL is valid ONLY for KAIHLE_ADMIN. All other roles require school_id.
    -- Enforced by: CHECK (role = 'KAIHLE_ADMIN' OR school_id IS NOT NULL)
    email               VARCHAR(255) NOT NULL,
    hashed_password     VARCHAR(255),
    -- NULL for magic-link-only users (invited teachers/parents)
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    role                user_role   NOT NULL,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    last_login_at       TIMESTAMPTZ,
    must_change_password BOOLEAN    NOT NULL DEFAULT FALSE,  -- v2.2: added
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    CONSTRAINT users_email_unique UNIQUE (email),
    CONSTRAINT chk_user_school_id_required CHECK (role = 'KAIHLE_ADMIN' OR school_id IS NOT NULL)
);

COMMENT ON TABLE users IS
    'All human users across all roles.
     school_id: NULL is valid ONLY for KAIHLE_ADMIN (platform-level role with no school).
     All other roles (STUDENT, TEACHER, SCHOOL_ADMIN, PARENT) MUST have school_id.
     Enforced by CHECK constraint: CHECK (role = ''KAIHLE_ADMIN'' OR school_id IS NOT NULL).
     hashed_password NULL: user authenticates via magic link only.
     email UNIQUE: globally unique, not per-school (simplifies magic link auth).
     must_change_password (v2.2): set TRUE after password reset to force change on next login.';

CREATE INDEX idx_users_school_role ON users (school_id, role);
CREATE INDEX idx_users_email       ON users (email);

-- ---------------------------------------------------------------------------

CREATE TABLE auth_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash  TEXT        NOT NULL,  -- SHA-256 hash of raw token, never store raw
    type        auth_token_type NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,           -- NULL = not yet used. Set on first use.
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT auth_tokens_hash_unique UNIQUE (token_hash)
);

COMMENT ON TABLE auth_tokens IS
    'Magic link and refresh token storage.
     token_hash: SHA-256 of raw token. Raw token travels in email/header, never stored.
     used_at: tokens are single-use. Second use returns 401.
     Nightly Celery task purges expired tokens.
     type=PASSWORD_RESET (v2.2): token issued for password reset flow.';

CREATE INDEX idx_auth_tokens_user    ON auth_tokens (user_id);
CREATE INDEX idx_auth_tokens_expires ON auth_tokens (expires_at);

-- ---------------------------------------------------------------------------

CREATE TABLE parent_student (
    parent_id   UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    student_id  UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (parent_id, student_id),
    CONSTRAINT chk_ps_not_same CHECK (parent_id <> student_id)
);

COMMENT ON TABLE parent_student IS
    'Explicit many-to-many link: parent → child students.
     One parent can have multiple children. One student can have multiple parents.
     Managed by School Admin.
     Parent portal: shows only data for students linked here.';

-- ---------------------------------------------------------------------------

CREATE TABLE student_profiles (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                         UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    grade_id                        UUID REFERENCES grades (id) ON DELETE SET NULL,
    -- grade_id: current grade. Also derivable via class_enrollments → classes.
    -- Stored here for fast access without join (e.g. Parent Portal header).
    age                             INT,
    -- v2.1: is_learning_profile_complete tracks whether student has submitted
    -- the learning profile questionnaire. Required for dashboard access.
    is_learning_profile_complete    BOOLEAN NOT NULL DEFAULT FALSE,
    -- NOTE: onboarding_diagnostic_status REMOVED in v2.1 - moved to class_enrollments
    -- A student is fully diagnostically onboarded when ALL active class_enrollments
    -- have onboarding_diagnostic_status = 'COMPLETED'
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ,
    CONSTRAINT sp_user_unique UNIQUE (user_id)
);

COMMENT ON TABLE student_profiles IS
    'Extended profile for student users.
     curriculum_id REMOVED from v1 — curriculum is derived from class enrollment.
     A student enrolled in a Cambridge class takes Cambridge diagnostics.
     No redundant curriculum storage.
     v2.1: replaced has_completed_onboarding BOOLEAN + learning_profile JSONB
     with separate student_learning_profiles table.
     v2.1: added is_learning_profile_complete BOOLEAN to track questionnaire completion.
     onboarding_diagnostic_status moved to class_enrollments table (per-class tracking).';

-- ---------------------------------------------------------------------------

CREATE TABLE teacher_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    qualifications  JSONB,
    experience_years INT,
    bio             TEXT,
    hire_date       DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT tp_user_unique UNIQUE (user_id)
);

-- ---------------------------------------------------------------------------
-- student_learning_profiles: normalised learning profile per student.
-- Created during onboarding (step 1 of 2) via the learning profile questionnaire.
-- Replaces the old learning_profile JSONB blob on student_profiles.
-- Used by: content_curator.py (resource weighting) and quiz_generator.py (interest injection).
-- ---------------------------------------------------------------------------

CREATE TABLE student_learning_profiles (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id              UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    school_id               UUID        NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
    -- school_id: tenant isolation — every non-curriculum table must have school_id
    modality_scores         JSONB       NOT NULL DEFAULT '{}',
    -- Scores per modality, range 0.0–1.0. Multiple high scores are valid.
    -- Derived from questionnaire Q1 + Q2 (see scoring logic in onboarding_service.py).
    -- { "visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5 }
    -- visual:          prefers diagrams, charts, videos
    -- auditory:        prefers listening, discussion
    -- reading_writing: prefers text, articles, writing notes
    -- kinesthetic:     prefers exercises, hands-on, interactive tools
    work_style              JSONB       NOT NULL DEFAULT '{}',
    -- { "prefers_solo": true, "short_sessions": false,
    --   "task_based": true, "concept_first": false }
    -- Derived from questionnaire Q3–Q5.
    interests               TEXT[],
    -- Free-text interest tags, stored lowercase.
    -- e.g. ARRAY['football', 'music', 'gaming', 'cooking']
    -- Top 2 injected into quiz_generator.py LLM prompt for scenario personalisation.
    -- Derived from questionnaire Q6–Q10 (multi-select).
    questionnaire_version   VARCHAR(10) NOT NULL DEFAULT 'v1',
    -- Allows future questionnaire redesigns without data loss.
    -- If questionnaire changes materially, bump to 'v2' — old profiles remain valid.
    completed_at            TIMESTAMPTZ,
    -- NULL = questionnaire started but not submitted (student abandoned partway).
    -- Non-NULL = questionnaire fully submitted. Only non-NULL profiles are used by AI features.
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,
    -- NOTE: slp_student_unique and idx_slp_student both enforce uniqueness on student_id.
    -- Only one is needed. The UNIQUE constraint below serves as the authoritative enforcement.
    -- The idx_slp_student index is a duplicate and should be dropped.
    CONSTRAINT slp_student_unique UNIQUE (student_id)
    -- One profile per student. Use ON CONFLICT DO UPDATE to handle re-submission.
);

COMMENT ON TABLE student_learning_profiles IS
    'Normalised learning profile collected during student onboarding (Step 1 of 2).
     Replaces learning_profile JSONB blob on student_profiles (v2.0).
     completed_at IS NOT NULL = profile is usable by AI features.
     completed_at IS NULL = student started questionnaire but did not finish.
     Used by:
       content_curator.curate_resources() — modality_scores weight resource type ranking
         visual > 0.6 → VIDEO resources × 1.3 boost
         reading_writing > 0.6 → ARTICLE resources × 1.3 boost
         kinesthetic > 0.6 → INTERACTIVE resources × 1.3 boost
       quiz_generator.generate_quiz() — top 2 interests injected into LLM prompt
     Accessible to teacher in class gap map (read-only student panel).
     Accessible to student via /student/settings/profile (editable after onboarding).';

-- NOTE: idx_slp_student is a duplicate of the slp_student_unique constraint above.
-- Only the constraint is needed. This index should not be re-created on fresh installs.
CREATE INDEX idx_slp_school ON student_learning_profiles (school_id);

-- ---------------------------------------------------------------------------
-- classes: the operational unit for all school activity.
-- Each class = one teacher × one subject × one curriculum × one grade × one year.
-- This is the context for assessments, gap maps, lesson plans.
-- ---------------------------------------------------------------------------

CREATE TABLE classes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id       UUID        NOT NULL REFERENCES schools (id)    ON DELETE CASCADE,
    grade_id        UUID        NOT NULL REFERENCES grades (id)     ON DELETE RESTRICT,
    subject_id      UUID        NOT NULL REFERENCES subjects (id)   ON DELETE RESTRICT,
    curriculum_id   UUID        NOT NULL REFERENCES curricula (id)  ON DELETE RESTRICT,
    teacher_id      UUID        NOT NULL REFERENCES users (id)      ON DELETE RESTRICT,
    name            VARCHAR(100) NOT NULL,   -- e.g. "Grade 9 Math — Cambridge A"
    academic_year   VARCHAR(20)  NOT NULL,   -- e.g. "2025-2026"
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

COMMENT ON TABLE classes IS
    'Operational unit. One class = one teacher + one subject + one curriculum + one grade.
     School running Cambridge AND IB Math for Grade 9 has TWO class rows.
     curriculum_id must exist in school_curricula for this school — enforced at service layer.
     All assessments, gap_states, lesson_plans, and study_plans are class-scoped.';

CREATE INDEX idx_classes_school     ON classes (school_id);
CREATE INDEX idx_classes_teacher    ON classes (teacher_id);
CREATE INDEX idx_classes_active     ON classes (school_id, is_active);

-- ---------------------------------------------------------------------------

CREATE TABLE class_enrollments (
    class_id                       UUID    NOT NULL REFERENCES classes (id)  ON DELETE CASCADE,
    student_id                     UUID    NOT NULL REFERENCES users (id)    ON DELETE CASCADE,
    enrolled_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active                      BOOLEAN NOT NULL DEFAULT TRUE,
    -- is_active=FALSE: student left mid-term. Historical data preserved.
    onboarding_diagnostic_status   onboarding_status NOT NULL DEFAULT 'PENDING',
    -- PENDING:     student enrolled, Tier 1 diagnostic not yet completed for this class
    -- IN_PROGRESS: Tier 1 diagnostic created for this class, not yet completed
    -- COMPLETED:   Tier 1 diagnostic completed for this class
    -- A student is fully diagnostically onboarded when ALL active enrollments are COMPLETED
    PRIMARY KEY (class_id, student_id)
);

COMMENT ON TABLE class_enrollments IS
    'Many-to-many: students enrolled in classes.
     A student has one enrollment per subject (Math, Science, English = 3 enrollments).
     is_active=FALSE preserves historical data when a student withdraws.
     Count of active enrollments per school enforced against subscription.max_students.
     v2.1: Added onboarding_diagnostic_status to track diagnostic completion per class.';

CREATE INDEX idx_enrollments_student ON class_enrollments (student_id);
CREATE INDEX idx_enrollments_active  ON class_enrollments (class_id, is_active);
CREATE INDEX idx_enrollments_onboarding_status ON class_enrollments (student_id, onboarding_diagnostic_status);

-- ---------------------------------------------------------------------------
-- class_topics: teacher-configured topic list for a class (v2.2)
-- ---------------------------------------------------------------------------

CREATE TABLE class_topics (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id           UUID        NOT NULL REFERENCES schools (id) ON DELETE RESTRICT,
    class_id            UUID        NOT NULL REFERENCES classes (id) ON DELETE CASCADE,
    curriculum_topic_id UUID        NOT NULL REFERENCES curriculum_topics (id) ON DELETE RESTRICT,
    sequence_order      INT         NOT NULL,
    is_covered          BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_class_topic UNIQUE (class_id, curriculum_topic_id)
);

COMMENT ON TABLE class_topics IS
    'Teacher-selected topics for a specific class (v2.2).
     Allows teachers to configure which curriculum topics they cover and in what order.
     is_covered: teacher marks topic as delivered to class.
     Used by lesson plan generator to scope content selection.';

CREATE INDEX idx_class_topics_class  ON class_topics (class_id);
CREATE INDEX idx_class_topics_school ON class_topics (school_id);

-- =============================================================================
-- SECTION 4: ASSESSMENTS
-- Definition (teacher creates once for a class) is fully separated from
-- student_attempts (one per student, tracks individual progress).
-- =============================================================================

CREATE TABLE assessments (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id           UUID        NOT NULL REFERENCES schools (id) ON DELETE RESTRICT,
    -- v2.2: school_id added for tenant isolation
    class_id            UUID        NOT NULL REFERENCES classes (id) ON DELETE CASCADE,
    created_by          UUID        REFERENCES users (id) ON DELETE RESTRICT,
    -- nullable: system-created assessments may not have a human creator
    title               TEXT        NOT NULL,
    assessment_type     assessment_type NOT NULL,
    status              assessment_status NOT NULL DEFAULT 'DRAFT',
    -- v2.2: removed is_system_generated, curriculum_topic_id, config, due_at
    -- v2.2: added school_id, published_at, question_count, questions_per_topic,
    --        minimum_difficulty, maximum_difficulty, question_types, time_limit_minutes, deadline
    instructions        TEXT,
    published_at        TIMESTAMPTZ,
    question_count      INT,
    questions_per_topic INT         NOT NULL DEFAULT 5,
    -- minimum 3 per topic for statistical reliability (Vidhya rule)
    minimum_difficulty  INT         NOT NULL DEFAULT 1,
    maximum_difficulty  INT         NOT NULL DEFAULT 5,
    question_types      TEXT[]      NOT NULL DEFAULT ARRAY['MCQ', 'TRUE_FALSE'],
    time_limit_minutes  INT         NOT NULL DEFAULT 0,
    -- 0 = untimed
    deadline            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    CONSTRAINT chk_assessment_min_diff  CHECK (minimum_difficulty >= 1),
    CONSTRAINT chk_assessment_max_diff  CHECK (maximum_difficulty <= 5),
    CONSTRAINT chk_assessment_qpt       CHECK (questions_per_topic >= 1),
    CONSTRAINT chk_assessment_time_limit CHECK (time_limit_minutes >= 0)
);

COMMENT ON TABLE assessments IS
    'Assessment definition. Teacher creates once.
     Replaces v1 approach of one assessment row per student.
     v2.2: is_system_generated removed — all assessments are now teacher-created.
     v2.2: config JSONB replaced by typed columns (questions_per_topic, difficulty range, etc).
     v2.2: curriculum_topic_id moved to assessment_topic_config table (supports multi-topic).
     DRAFT: teacher selecting/previewing questions.
     ACTIVE: students can start. CLOSED: results visible, no new attempts.';

CREATE INDEX idx_assessments_school_id ON assessments (school_id);
CREATE INDEX idx_assessments_class     ON assessments (class_id);
CREATE INDEX idx_assessments_status    ON assessments (status);
CREATE INDEX idx_assessments_type      ON assessments (assessment_type);

-- ---------------------------------------------------------------------------
-- assessment_topic_config: topics selected for an assessment (v2.2)
-- Replaces the deprecated curriculum_topic_id single-FK column on assessments.
-- Supports multi-topic assessments and records which grade each topic came from.
-- ---------------------------------------------------------------------------

CREATE TABLE assessment_topic_config (
    assessment_id       UUID NOT NULL REFERENCES assessments (id)        ON DELETE CASCADE,
    curriculum_topic_id UUID NOT NULL REFERENCES curriculum_topics (id)  ON DELETE RESTRICT,
    grade_id            UUID NOT NULL REFERENCES grades (id)             ON DELETE RESTRICT,
    PRIMARY KEY (assessment_id, curriculum_topic_id)
);

COMMENT ON TABLE assessment_topic_config IS
    'Topics selected for an assessment — one row per topic per assessment (v2.2).
     Replaces single curriculum_topic_id column on assessments.
     grade_id: records which grade the topic came from — supports prior-grade topic selection
     (Tier 1 diagnostics probe current AND prior grade: grade = class.grade and class.grade - 1).';

CREATE INDEX idx_atc_assessment ON assessment_topic_config (assessment_id);

-- ---------------------------------------------------------------------------
-- assessment_selected_questions: which questions were chosen for this assessment.
-- ---------------------------------------------------------------------------

CREATE TABLE assessment_selected_questions (
    assessment_id   UUID NOT NULL REFERENCES assessments (id)    ON DELETE CASCADE,
    question_id     UUID NOT NULL REFERENCES question_bank (id)  ON DELETE RESTRICT,
    order_index     INT  NOT NULL,
    PRIMARY KEY (assessment_id, question_id),
    CONSTRAINT chk_asq_order CHECK (order_index >= 0)
);

COMMENT ON TABLE assessment_selected_questions IS
    'Bridge between assessment definition and question_bank.
     order_index: display order for students. Randomised at attempt-start, not here.
     Populated by assessment_service.create_assessment() from question bank + LLM fallback.';

CREATE INDEX idx_asq_assessment ON assessment_selected_questions (assessment_id);

-- ---------------------------------------------------------------------------
-- student_attempts: one row per student per assessment.
-- Created when student opens the assessment for the first time.
-- ---------------------------------------------------------------------------

CREATE TABLE student_attempts (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id       UUID        NOT NULL REFERENCES assessments (id)  ON DELETE CASCADE,
    student_id          UUID        NOT NULL REFERENCES users (id)        ON DELETE CASCADE,
    status              attempt_status NOT NULL DEFAULT 'NOT_STARTED',
    total_questions     INT,
    questions_answered  INT         NOT NULL DEFAULT 0,
    overall_score       FLOAT,      -- NULL until COMPLETED
    time_taken_seconds  INT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    CONSTRAINT sa_unique UNIQUE (assessment_id, student_id),
    -- One attempt per student per assessment. Use ON CONFLICT DO UPDATE on start.
    CONSTRAINT chk_sa_score CHECK (overall_score IS NULL OR (overall_score BETWEEN 0.0 AND 1.0))
);

COMMENT ON TABLE student_attempts IS
    'Per-student attempt. The progress_status field you requested is: status.
     NOT_STARTED: assignment visible but student has not opened it.
     IN_PROGRESS: student has started, some questions answered.
     COMPLETED: all questions answered and submitted.
     ABANDONED: student left, did not complete.
     On COMPLETED: triggers Celery task calculate_gap_states(attempt_id).';

CREATE INDEX idx_attempts_assessment ON student_attempts (assessment_id);
CREATE INDEX idx_attempts_student    ON student_attempts (student_id);
CREATE INDEX idx_attempts_status     ON student_attempts (status);

-- ---------------------------------------------------------------------------
-- student_responses: one row per question per attempt.
-- ---------------------------------------------------------------------------

CREATE TABLE student_responses (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id      UUID        NOT NULL REFERENCES student_attempts (id) ON DELETE CASCADE,
    question_id     UUID        NOT NULL REFERENCES question_bank (id)    ON DELETE RESTRICT,
    answer_given    TEXT,               -- NULL if question skipped
    is_correct      BOOLEAN,            -- NULL for SHORT_ANSWER until LLM scores it
    score           FLOAT,              -- 0.0–1.0. NULL until scored.
    scored_by       scored_by   NOT NULL DEFAULT 'PENDING',
    ai_feedback     TEXT,               -- LLM justification for SHORT_ANSWER scoring
    hints_used      INT         NOT NULL DEFAULT 0,
    time_taken_ms   INT,
    answered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sr_unique UNIQUE (attempt_id, question_id),
    CONSTRAINT chk_sr_score CHECK (score IS NULL OR score BETWEEN 0.0 AND 1.0)
);

COMMENT ON TABLE student_responses IS
    'Per-question response within an attempt.
     MCQ/TRUE_FALSE: scored immediately (scored_by=RULE), is_correct set synchronously.
     SHORT_ANSWER: scored_by=PENDING on insert, Celery updates to LLM + sets score.
     ai_feedback: stored for SHORT_ANSWER — shown to student after submission.';

CREATE INDEX idx_responses_attempt  ON student_responses (attempt_id);
CREATE INDEX idx_responses_question ON student_responses (question_id);
CREATE INDEX idx_responses_scored   ON student_responses (scored_by)
    WHERE scored_by = 'PENDING';  -- partial index for pending scoring queue

-- =============================================================================
-- SECTION 5: GAP STATES
-- Replaces v1 student_knowledge_profiles.
-- One row per student × subtopic × class.
-- Updated after every completed attempt and every study plan quiz.
-- =============================================================================

CREATE TABLE gap_states (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID        NOT NULL REFERENCES users (id)     ON DELETE CASCADE,
    subtopic_id     UUID        NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    class_id        UUID        NOT NULL REFERENCES classes (id)   ON DELETE CASCADE,
    -- class_id: A student in Cambridge Math AND IB Math has separate gap_states per class.
    mastery_score   FLOAT       NOT NULL DEFAULT 0.0,
    -- 0.0–1.0 rolling average.
    -- < 0.4: Needs Work (Red) | 0.4–0.7: Developing (Amber) | > 0.7: Strong (Green)
    confidence      FLOAT       NOT NULL DEFAULT 0.0,
    -- 0.0–1.0. Grows with attempt_count. Low confidence = insufficient data points.
    attempt_count   INT         NOT NULL DEFAULT 0,
    total_correct   INT         NOT NULL DEFAULT 0,
    total_attempted INT         NOT NULL DEFAULT 0,
    needs_review    BOOLEAN     NOT NULL DEFAULT TRUE,
    last_assessed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT gap_states_unique
        UNIQUE (student_id, subtopic_id, class_id),
    CONSTRAINT chk_gs_mastery    CHECK (mastery_score BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_gs_confidence CHECK (confidence BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_gs_counts     CHECK (total_correct <= total_attempted)
);

COMMENT ON TABLE gap_states IS
    'Normalised mastery tracking. Replaces v1 student_knowledge_profiles JSONB blobs.
     Updated by Celery task: calculate_gap_states(attempt_id) after each attempt.
     Also updated when student completes a study_plan_quiz.
     mastery_score drives:
       - Gap Map cell colours (teacher dashboard)
       - Study plan prioritisation (lowest mastery first)
       - Student grouping for lesson plans (Group A < 0.4, B 0.4–0.7, C > 0.7)
       - Parent report narrative (which subtopics improved, which need work)';

CREATE INDEX idx_gap_states_student       ON gap_states (student_id);
CREATE INDEX idx_gap_states_subtopic      ON gap_states (subtopic_id);
CREATE INDEX idx_gap_states_class         ON gap_states (class_id);
CREATE INDEX idx_gap_states_student_class ON gap_states (student_id, class_id);
CREATE INDEX idx_gap_states_mastery       ON gap_states (mastery_score);

-- =============================================================================
-- SECTION: CONTENT LAYER (subtopic_content, interest_categories)
-- Replaces deprecated curriculum_chunks PDF RAG approach.
-- No pgvector, no embeddings — structured SQL retrieval only.
-- =============================================================================

CREATE TABLE interest_categories (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- v2.2: changed from regular index to UNIQUE index (name already has UNIQUE constraint above)
CREATE UNIQUE INDEX idx_interest_categories_name ON interest_categories (name);

COMMENT ON TABLE interest_categories IS
    'Lookup table for content personalisation tags.
     Seeded by KaihleAdmin. Referenced by subtopic_content.interest_category_id.
     Values are human-readable labels e.g. "sport", "technology", "arts".
     Distinct from student_learning_profiles.interests TEXT[] which are student free-text tags.';

-- ---------------------------------------------------------------------------

CREATE TABLE subtopic_content (
    id                              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    subtopic_id                     UUID        NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    content_type                    content_type NOT NULL,
    -- v2.2: changed from VARCHAR(50) to content_type enum

    -- Video fields (content_type = 'video')
    video_url                       TEXT,
    video_provider                  TEXT,
    video_duration_seconds          INT,
    video_thumbnail_url             TEXT,
    videos                          JSONB,
    -- Array of video candidates: [{url, title, channel, view_count, status, last_checked_at}]

    -- Explanation fields (content_type = 'explanation')
    explanation_text                TEXT,

    -- Practice / quiz fields (content_type = 'practice' | 'quiz')
    quiz_questions                  JSONB,
    -- [{question_id, question_text, options, correct_answer, explanation}]
    quiz_questions_count            INT,
    CONSTRAINT ck_quiz_questions_count_positive CHECK (quiz_questions_count >= 0),

    -- Teacher-authored explanation (overrides explanation_text when present)
    teacher_explanation             TEXT,
    teacher_explanation_author_id   UUID REFERENCES users (id) ON DELETE SET NULL,

    -- Personalisation
    interest_category_id            UUID REFERENCES interest_categories (id) ON DELETE SET NULL,
    applicable_tiers                INT[] NOT NULL DEFAULT '{1,2,3}',

    -- Review workflow (KaihleAdmin approves videos; teacher approves explanations)
    review_status                   review_status NOT NULL DEFAULT 'pending',
    -- v2.2: changed from VARCHAR(20) to review_status enum
    reviewed_at                     TIMESTAMPTZ,
    reviewed_by_id                  UUID REFERENCES users (id) ON DELETE SET NULL,
    rejection_reason                TEXT,
    rejection_teacher_note          TEXT,       -- v2.2: added (teacher-visible rejection note)

    -- Student feedback aggregates (denormalised for read performance)
    thumbs_up_count                 INT NOT NULL DEFAULT 0,     -- v2.2: added
    thumbs_down_count               INT NOT NULL DEFAULT 0,     -- v2.2: added

    -- Status flags
    is_active                       BOOLEAN NOT NULL DEFAULT TRUE,
    is_stale                        BOOLEAN NOT NULL DEFAULT FALSE,
    is_archived                     BOOLEAN NOT NULL DEFAULT FALSE,

    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ
);

CREATE INDEX idx_subtopic_content_subtopic    ON subtopic_content (subtopic_id);
CREATE INDEX idx_subtopic_content_type        ON subtopic_content (content_type);
CREATE INDEX idx_subtopic_content_review      ON subtopic_content (review_status);
CREATE INDEX idx_subtopic_content_active      ON subtopic_content (is_active);
CREATE INDEX idx_subtopic_content_interest    ON subtopic_content (interest_category_id);

-- v2.2: partial unique indexes — one active approved content per type per subtopic
CREATE UNIQUE INDEX uix_subtopic_content_active_explanation
    ON subtopic_content(subtopic_id) WHERE content_type = 'explanation' AND review_status = 'approved';
CREATE UNIQUE INDEX uix_subtopic_content_active_video
    ON subtopic_content(subtopic_id) WHERE content_type = 'video' AND review_status = 'approved';
CREATE UNIQUE INDEX uix_subtopic_content_active_practice
    ON subtopic_content(subtopic_id) WHERE content_type = 'practice' AND review_status = 'approved';

COMMENT ON TABLE subtopic_content IS
    'One row per (subtopic, content_type) combination — curriculum layer, no school_id.
     Replaces curriculum_chunks PDF/RAG approach.
     content_type values (v2.2 enum): video | explanation | practice | quiz.
     review_status (v2.2 enum): pending → approved | rejected.
     KaihleAdmin reviews video content. Teachers review explanation content.
     applicable_tiers: [1,2,3] means content applies to all student tiers.
     thumbs_up/down_count (v2.2): denormalised feedback aggregates from subtopic_content_feedback.
     rejection_teacher_note (v2.2): teacher-visible explanation when content is rejected.';

-- =============================================================================
-- SECTION: STUDENT LESSON PACKS
-- Generated collections of content for individual students.
-- school_id present (tenant-scoped).
-- =============================================================================

CREATE TYPE pack_type_enum    AS ENUM ('quiz', 'video', 'explanation', 'mixed');
CREATE TYPE pack_status_enum  AS ENUM ('generated', 'sent', 'in_progress', 'completed', 'expired');

CREATE TABLE student_lesson_packs (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id                  UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    school_id                   UUID        NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
    content_ids                 UUID[]      NOT NULL,
    -- Array of subtopic_content.id references
    subtopic_ids                UUID[]      NOT NULL,
    -- Denormalised for fast lookup
    title                       TEXT        NOT NULL,
    pack_type                   pack_type_enum NOT NULL DEFAULT 'mixed',
    target_tier                 INT         NOT NULL,
    mastery_score               NUMERIC(5,4),
    status                      pack_status_enum NOT NULL DEFAULT 'generated',
    generated_by_teacher_id     UUID,
    expires_at                  TIMESTAMPTZ,
    sent_at                     TIMESTAMPTZ,
    started_at                  TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,
    is_archived                 BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_slp_student    ON student_lesson_packs (student_id);
CREATE INDEX idx_slp_school     ON student_lesson_packs (school_id);
CREATE INDEX idx_slp_status     ON student_lesson_packs (status);
CREATE INDEX idx_slp_expires    ON student_lesson_packs (expires_at);
CREATE INDEX idx_slp_archived   ON student_lesson_packs (is_archived);

COMMENT ON TABLE student_lesson_packs IS
    'Generated content packs for individual students.
     content_ids: array of subtopic_content.id — the actual content to deliver.
     subtopic_ids: denormalised for fast gap-map correlation.
     pack_type: quiz | video | explanation | mixed.
     target_tier: 1 | 2 | 3 — determines which subtopic_content rows are eligible.
     status lifecycle: generated → sent → in_progress → completed | expired.';

-- =============================================================================
-- SECTION: ASSESSMENT SCORING DETAIL
-- Per-attempt, per-subtopic scores for recency-weighted mastery calculation.
-- =============================================================================

CREATE TABLE student_attempt_subtopic_scores (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subtopic_id     UUID        NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    attempt_id      UUID        NOT NULL REFERENCES student_attempts (id) ON DELETE CASCADE,
    score           FLOAT       NOT NULL,
    -- Per-subtopic fraction correct for this attempt: correct / total for subtopic
    attempted_at    TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_sats_student_subtopic_attempt UNIQUE (student_id, subtopic_id, attempt_id),
    CONSTRAINT chk_sats_score CHECK (score BETWEEN 0.0 AND 1.0)
);

CREATE INDEX idx_subtopic_scores_student_sub ON student_attempt_subtopic_scores (student_id, subtopic_id);

COMMENT ON TABLE student_attempt_subtopic_scores IS
    'Inserted by calculate_gap_states Celery task after each COMPLETED attempt.
     Stores per-subtopic score for that attempt (correct / total for that subtopic).
     Used to compute recency-weighted mastery in subsequent gap state calculations.
     Distinct from gap_states which holds the rolling aggregate.';

-- =============================================================================
-- SECTION: MINI-COURSE PROGRESS AND FEEDBACK (v2.2)
-- Tracks student engagement with mini-course content (explanations, videos, practice).
-- =============================================================================

CREATE TABLE subtopic_course_progress (
    student_id              UUID    NOT NULL REFERENCES users (id)     ON DELETE CASCADE,
    subtopic_id             UUID    NOT NULL REFERENCES subtopics (id) ON DELETE CASCADE,
    school_id               UUID    NOT NULL REFERENCES schools (id)   ON DELETE RESTRICT,
    last_visited_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    explanation_accessed    BOOLEAN NOT NULL DEFAULT FALSE,
    video_accessed          BOOLEAN NOT NULL DEFAULT FALSE,
    check_questions_score   FLOAT,
    -- NULL until student completes the check questions for this subtopic
    PRIMARY KEY (student_id, subtopic_id)
);

COMMENT ON TABLE subtopic_course_progress IS
    'Tracks a student''s progress through a mini-course for a given subtopic (v2.2).
     One row per (student, subtopic) — updated every time student opens the mini-course page.
     check_questions_score: NULL until check questions completed (0.0–1.0).
     Used to surface progress indicators in Student class view.';

CREATE INDEX idx_subtopic_course_progress_school_student
    ON subtopic_course_progress (school_id, student_id);

-- ---------------------------------------------------------------------------

CREATE TABLE subtopic_content_feedback (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id              UUID        NOT NULL REFERENCES users (id)              ON DELETE CASCADE,
    subtopic_content_id     UUID        NOT NULL REFERENCES subtopic_content (id)  ON DELETE CASCADE,
    school_id               UUID        NOT NULL REFERENCES schools (id)            ON DELETE CASCADE,
    feedback_type           VARCHAR(20) NOT NULL,
    comment                 TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_subtopic_content_feedback_student_content UNIQUE (student_id, subtopic_content_id),
    CONSTRAINT chk_subtopic_content_feedback_type CHECK (feedback_type IN ('thumbs_up', 'thumbs_down'))
);

COMMENT ON TABLE subtopic_content_feedback IS
    'Student thumbs-up/thumbs-down feedback on subtopic content (v2.2).
     UNIQUE on (student_id, subtopic_content_id) — one feedback per student per content row.
     feedback_type: thumbs_up | thumbs_down.
     Aggregated into subtopic_content.thumbs_up_count and thumbs_down_count.';

CREATE INDEX idx_scf_subtopic_content ON subtopic_content_feedback (subtopic_content_id);
CREATE INDEX idx_scf_school           ON subtopic_content_feedback (school_id);

-- SECTION 6: STUDY PLANS
-- =============================================================================

CREATE TABLE study_plans (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id  UUID        NOT NULL REFERENCES users (id)     ON DELETE CASCADE,
    subtopic_id UUID        NOT NULL REFERENCES subtopics (id) ON DELETE RESTRICT,
    class_id    UUID        NOT NULL REFERENCES classes (id)   ON DELETE CASCADE,
    assigned_by UUID        NOT NULL REFERENCES users (id)     ON DELETE RESTRICT,
    status      study_plan_status NOT NULL DEFAULT 'GENERATING',
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

COMMENT ON TABLE study_plans IS
    'One study plan per student per subtopic per class.
     Assigned by teacher from Gap Map (click red cell → Assign Study Plan).
     GENERATING: Celery task curating resources + generating quiz.
     ACTIVE: student can view resources and take quiz.
     COMPLETED: student finished. Triggers gap_state recalculation.';

CREATE INDEX idx_study_plans_student  ON study_plans (student_id);
CREATE INDEX idx_study_plans_subtopic ON study_plans (subtopic_id);
CREATE INDEX idx_study_plans_class    ON study_plans (class_id);

-- ---------------------------------------------------------------------------

CREATE TABLE study_plan_resources (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         UUID        NOT NULL REFERENCES study_plans (id) ON DELETE CASCADE,
    resource_type   resource_type NOT NULL,
    title           TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    description     TEXT,
    duration_seconds INT,
    alignment_score FLOAT,
    -- cosine_sim(resource_embed, subtopic.embedding). Threshold: > 0.72 to be included.
    order_index     INT         NOT NULL,
    is_watched      BOOLEAN     NOT NULL DEFAULT FALSE,
    watched_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_spr_alignment CHECK (alignment_score IS NULL OR alignment_score BETWEEN 0.0 AND 1.0)
);

COMMENT ON TABLE study_plan_resources IS
    'Curated external resources (2-3 per plan) sourced by content_curator.py.
     Sources: YouTube Data API v3, Khan Academy, static curated index.
     alignment_score: cosine similarity to subtopic.embedding. Min threshold 0.72.
     Ordered by alignment_score DESC.
     is_watched: student marks as done before quiz is unlocked.';

CREATE INDEX idx_spr_plan ON study_plan_resources (plan_id);

-- ---------------------------------------------------------------------------

CREATE TABLE study_plan_quizzes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         UUID NOT NULL REFERENCES study_plans (id) ON DELETE CASCADE,
    questions       JSONB NOT NULL,
    -- 5 questions generated by quiz_generator.py using subtopic.embedding for RAG
    -- [{
    --   "index": 0, "question_text": "...", "type": "MCQ",
    --   "options": [{"key": "A", "text": "..."},...],
    --   "correct_answer": "A", "explanation": "..."
    -- }]
    student_answers JSONB,
    -- [{index: 0, answer: "A", is_correct: true, score: 1.0}]
    -- NULL until student submits
    score           FLOAT,          -- 0.0–1.0 aggregate. NULL until submitted.
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT spq_plan_unique UNIQUE (plan_id),
    CONSTRAINT chk_spq_score CHECK (score IS NULL OR score BETWEEN 0.0 AND 1.0)
);

COMMENT ON TABLE study_plan_quizzes IS
    'AI-generated quiz. One quiz per study plan.
     Generated by quiz_generator.py: 4 MCQ + 1 SHORT_ANSWER, calibrated to student mastery.
     questions: stored as JSONB (ephemeral, not reused in question_bank).
     On completion: scoring_service scores it, gap_state recalculated for subtopic.';

-- =============================================================================
-- SECTION 7: TEACHER COPILOT — LESSON PLANS
-- =============================================================================

CREATE TABLE lesson_plans (
    id                      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id                UUID    NOT NULL REFERENCES classes (id) ON DELETE CASCADE,
    teacher_id              UUID    NOT NULL REFERENCES users (id)   ON DELETE RESTRICT,
    week_start              DATE,
    -- v2.2: nullable (one-off plans need not be tied to a week)
    focus_subtopic_ids      UUID[]  NOT NULL DEFAULT '{}',
    -- Top 2 subtopic_ids with lowest class-average mastery this week
    class_context_snapshot  JSONB   NOT NULL DEFAULT '{}',
    -- v2.2: replaces gap_summary — richer snapshot including class composition, learning styles
    generated_plan          JSONB   NOT NULL DEFAULT '{}',
    -- Full lesson plan structure — see product_plan.md Part 4 for JSON schema
    teacher_edits           JSONB,
    -- Teacher's modifications. UI merges generated_plan + teacher_edits for display.
    status                  lesson_plan_status NOT NULL DEFAULT 'GENERATING',
    -- v2.2: status now includes GENERATING as initial state
    duration_minutes        INT     NOT NULL DEFAULT 45,
    -- v2.2: explicit duration (default 45 min)
    failure_code            lesson_plan_failure_code,
    -- v2.2: set on generation failure; NULL on success
    failure_reason          TEXT,
    -- v2.2: human-readable failure message; NULL on success
    raw_llm_output          TEXT,
    -- v2.2: raw LLM response stored for debugging and reprocessing
    generated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
    -- NOTE: lp_class_week_unique constraint REMOVED in v2.2
    -- Multiple lesson plans per class per week are now allowed (on-demand generation)
);

COMMENT ON TABLE lesson_plans IS
    'On-demand AI-generated lesson plan per class (v2.2).
     v2.1 was weekly Celery-scheduled; v2.2 is teacher-triggered on-demand.
     lp_class_week_unique REMOVED — teachers can generate multiple plans per week.
     week_start now nullable — one-off plans may not be tied to a specific week.
     gap_summary REMOVED and replaced by class_context_snapshot (richer context).
     failure_code / failure_reason: set when LLM generation fails.
     raw_llm_output: stored for debugging and potential retry/reprocessing.';

CREATE INDEX idx_lesson_plans_class   ON lesson_plans (class_id);
CREATE INDEX idx_lesson_plans_teacher ON lesson_plans (teacher_id);
CREATE INDEX idx_lesson_plans_week    ON lesson_plans (week_start);

-- =============================================================================
-- SECTION 8: PARENT PORTAL
-- =============================================================================

CREATE TABLE parent_report_snapshots (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID    NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    week_start      DATE    NOT NULL,
    narrative       TEXT    NOT NULL,
    -- Plain language, ~150 words, generated by Gemini Flash
    gap_summary     JSONB   NOT NULL DEFAULT '{}',
    -- [{"subtopic": "Quadratic Equations", "mastery": 0.45,
    --   "label": "Developing", "trend": "improving"}]
    improvements    JSONB,  -- top 2 subtopics that improved this week vs last snapshot
    needs_work      JSONB,  -- top 2 subtopics still below mastery threshold
    email_sent_at   TIMESTAMPTZ,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT prp_student_week_unique UNIQUE (student_id, week_start)
);

COMMENT ON TABLE parent_report_snapshots IS
    'Weekly parent narrative. Generated every Sunday 18:00 by Celery beat.
     Sent via Resend to all parents linked in parent_student for this student.
     narrative: plain English, no edu-jargon, 150-word limit in prompt.
     Stored for historical review in parent portal.
     improvements/needs_work: delta vs previous snapshot for trend language.';

CREATE INDEX idx_parent_reports_student ON parent_report_snapshots (student_id);
CREATE INDEX idx_parent_reports_week    ON parent_report_snapshots (week_start);

-- =============================================================================
-- SECTION 9: BILLING (per-school — completely redesigned from v1)
-- =============================================================================

CREATE TABLE subscription_plans (
    id                          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    tier                        subscription_tier NOT NULL,
    name                        VARCHAR(100) NOT NULL,
    description                 TEXT,
    price_per_student_annual    NUMERIC(10,2) NOT NULL,
    -- Starter: 75.00 | Growth: 100.00 | Scale: 125.00
    max_students                INT,
    -- Starter: 100 | Growth: 500 | Scale: NULL (unlimited)
    trial_days                  INT,
    -- TRIAL tier only: 15 days. NULL for paid tiers.
    max_curricula               INT,
    -- Starter: 1 | Growth: 2 | Scale: NULL (unlimited)
    features                    JSONB NOT NULL DEFAULT '{}',
    -- {
    --   "parent_portal": true,
    --   "teacher_copilot": true,
    --   "api_access": false,
    --   "sla_guarantee": false,
    --   "dedicated_support": false
    -- }
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order                  INT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ,
    CONSTRAINT sp_tier_unique UNIQUE (tier)
);

COMMENT ON TABLE subscription_plans IS
    'Pricing tier definitions. Seeded by Kaihle Admin at launch.
     Enforced at service layer:
       billing.check_student_limit(school_id) blocks enrollment when max_students exceeded.
       billing.check_curriculum_limit(school_id) blocks new curriculum adoption when exceeded.
     Trial: 15 days, max 30 students, full feature access.';

-- ---------------------------------------------------------------------------

CREATE TABLE school_subscriptions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id       UUID        NOT NULL REFERENCES schools (id)            ON DELETE RESTRICT,
    plan_id         UUID        NOT NULL REFERENCES subscription_plans (id) ON DELETE RESTRICT,
    status          subscription_status NOT NULL DEFAULT 'ACTIVE',
    billing_cycle   VARCHAR(20) NOT NULL DEFAULT 'annual',  -- 'annual' | 'monthly'
    student_count   INT         NOT NULL,   -- agreed headcount at subscription time
    total_amount    NUMERIC(10,2) NOT NULL, -- student_count × price_per_student
    currency        CHAR(3)     NOT NULL DEFAULT 'USD',
    start_date      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_date        TIMESTAMPTZ NOT NULL,   -- start_date + 1 year for annual
    trial_end_date  TIMESTAMPTZ,            -- NULL for non-trial plans
    payment_status  payment_status NOT NULL DEFAULT 'PENDING',
    external_ref    VARCHAR(200),           -- Stripe subscription ID
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

COMMENT ON TABLE school_subscriptions IS
    'Per-school subscription. Replaces v1 per-student subscriptions.
     student_count: headcount at subscription time. Limits class_enrollments (active count).
     total_amount = student_count × price_per_student_annual at time of subscription.
     One active subscription per school enforced at service layer.
     external_ref: Stripe subscription ID for webhook reconciliation.';

CREATE INDEX idx_school_sub_school ON school_subscriptions (school_id);
CREATE INDEX idx_school_sub_status ON school_subscriptions (status);

-- ---------------------------------------------------------------------------

CREATE TABLE subscription_invoices (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID        NOT NULL REFERENCES school_subscriptions (id) ON DELETE RESTRICT,
    school_id       UUID        NOT NULL REFERENCES schools (id)               ON DELETE RESTRICT,
    invoice_number  VARCHAR(50) NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    student_count   INT         NOT NULL,   -- headcount at invoice time (may differ from subscription)
    amount          NUMERIC(10,2) NOT NULL,
    currency        CHAR(3)     NOT NULL DEFAULT 'USD',
    status          payment_status NOT NULL DEFAULT 'PENDING',
    due_date        TIMESTAMPTZ NOT NULL,
    paid_at         TIMESTAMPTZ,
    pdf_url         VARCHAR(500),
    external_ref    VARCHAR(200),           -- Stripe invoice ID
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT inv_number_unique UNIQUE (invoice_number)
);

COMMENT ON TABLE subscription_invoices IS
    'One invoice per billing cycle per school.
     student_count captured at invoice time — may differ from subscription headcount
     if school grew their enrollment during the year.
     Annual billing: one invoice per year. Monthly: twelve invoices per year.';

CREATE INDEX idx_invoices_school       ON subscription_invoices (school_id);
CREATE INDEX idx_invoices_subscription ON subscription_invoices (subscription_id);
CREATE INDEX idx_invoices_status       ON subscription_invoices (status);

-- ---------------------------------------------------------------------------

CREATE TABLE trial_extensions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id         UUID NOT NULL
                                REFERENCES school_subscriptions (id) ON DELETE CASCADE,
    extended_by_admin_id    UUID NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    original_trial_end      TIMESTAMPTZ NOT NULL,
    new_trial_end           TIMESTAMPTZ NOT NULL,
    extension_days          INT NOT NULL,
    reason                  TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_te_days CHECK (extension_days > 0),
    CONSTRAINT chk_te_direction CHECK (new_trial_end > original_trial_end)
);

COMMENT ON TABLE trial_extensions IS
    'Audit trail for trial extensions granted by Kaihle Admin.
     Allows Vibhu to extend trials for prospect schools without code changes.';

-- =============================================================================
-- ALEMBIC
-- =============================================================================

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- =============================================================================
-- CHANGE SUMMARY vs v2.1
-- =============================================================================
--
-- ENUMS ADDED:
--   lesson_plan_failure_code    llm_auth_error | llm_rate_limit_error | llm_connection_error
--                               | llm_unexpected_error | json_parse_failed | class_not_found
--   content_type                video | explanation | practice | quiz
--   review_status               pending | approved | rejected
--
-- ENUM MODIFIED:
--   auth_token_type             PASSWORD_RESET value added
--   lesson_plan_status          GENERATING value added
--
-- COLUMN ADDED — users:
--   must_change_password BOOLEAN NOT NULL DEFAULT FALSE
--
-- TABLE CHANGED — assessments:
--   REMOVED: is_system_generated, curriculum_topic_id, config, due_at
--   ADDED:   school_id, published_at, question_count, questions_per_topic,
--             minimum_difficulty, maximum_difficulty, question_types,
--             time_limit_minutes, deadline
--   INDEX:   idx_assessments_school_id added
--
-- TABLE ADDED — assessment_topic_config:
--   Replaces single curriculum_topic_id FK on assessments.
--   Supports multi-topic assessments and prior-grade topic selection.
--
-- TABLE CHANGED — lesson_plans:
--   REMOVED: gap_summary column
--   REMOVED: lp_class_week_unique UNIQUE constraint
--   CHANGED: week_start made nullable (was NOT NULL)
--   ADDED:   class_context_snapshot JSONB NOT NULL DEFAULT '{}'
--   ADDED:   duration_minutes INT NOT NULL DEFAULT 45
--   ADDED:   failure_code lesson_plan_failure_code (nullable)
--   ADDED:   failure_reason TEXT (nullable)
--   ADDED:   raw_llm_output TEXT (nullable)
--
-- TABLE CHANGED — subtopic_content:
--   CHANGED: content_type VARCHAR(50) → content_type enum (content_type)
--   CHANGED: review_status VARCHAR(20) → review_status enum (review_status)
--   ADDED:   thumbs_up_count INT NOT NULL DEFAULT 0
--   ADDED:   thumbs_down_count INT NOT NULL DEFAULT 0
--   ADDED:   rejection_teacher_note TEXT
--   ADDED:   CHECK constraint on quiz_questions_count >= 0
--   ADDED:   3 partial UNIQUE indexes (one active approved per content_type per subtopic)
--
-- TABLE CHANGED — subjects:
--   ADDED:   subject_family_code VARCHAR(20)
--   INDEX:   idx_subjects_family_code added
--
-- TABLE CHANGED — curriculum_chunks:
--   ADDED:   updated_at TIMESTAMPTZ
--
-- TABLE ADDED — class_topics:
--   Teacher-configured topic list per class with sequence ordering.
--
-- TABLE ADDED — subtopic_course_progress:
--   Tracks student engagement with mini-course content per subtopic.
--
-- TABLE ADDED — subtopic_content_feedback:
--   Student thumbs-up/thumbs-down on AI-generated content.
--
-- INDEX CHANGED — student_learning_profiles:
--   NOTE: slp_student_unique constraint and idx_slp_student are duplicates.
--   The UNIQUE constraint (slp_student_unique) is authoritative.
--   idx_slp_student should be dropped on existing installations.
--
-- INDEX CHANGED — interest_categories:
--   idx_interest_categories_name changed from regular to UNIQUE index.
--   (Redundant with the UNIQUE constraint on name, but explicit for clarity.)
--
-- =============================================================================
-- CHANGE SUMMARY vs v1.0 (preserved from v2.1)
-- =============================================================================
--
-- KEPT (verbatim or minor adjustments):
--   curricula, subjects, grades, topics
--   curriculum_subjects, curriculum_topics (your proposed pivot table)
--   subtopics (+ embedding VECTOR(768) added, + curriculum_topic_id FK already existed)
--   topic_prerequisites → replaced by subtopic_prerequisites (more granular)
--   question_bank (simplified: only subtopic_id FK, removed topic_id/subject_id/grade_id)
--   schools (minor cleanup: added timezone, split contact fields)
--   users (added first_name/last_name split, cleaned up username)
--
-- REDESIGNED:
--   assessments        v1: one row per student. v2: class-level definition
--   student_knowledge_profiles → gap_states (normalised, not JSONB blobs)
--   study_plans        v1: JSONB blobs. v2: normalised with subtopic_id + class_id
--   subscriptions      v1: per-student. v2: per-school with invoicing
--
-- ADDED:
--   school_curricula              multi-curriculum per school (Q1)
--   classes + class_enrollments   school operational structure
--   auth_tokens                   magic link + refresh token storage
--   parent_student                explicit parent-child links (was field on student_profiles)
--   teacher_profiles              extended teacher data (separated from users)
--   student_attempts              per-student attempt (split from assessments)
--   student_responses             per-question response (replaces assessment_questions)
--   assessment_selected_questions assessment ↔ question_bank bridge
--   subtopic_prerequisites        prerequisite graph at atomic level
--   curriculum_chunks             PDF-sourced RAG chunks (added M2, not required pilot)
--   study_plan_resources          curated external resources
--   study_plan_quizzes            AI-generated practice quizzes
--   lesson_plans                  Teacher Copilot output
--   parent_report_snapshots       Parent Portal weekly narratives
--   subscription_plans            tier definitions (per-school)
--   school_subscriptions          per-school subscription (replaces subscriptions)
--   subscription_invoices         per-school invoicing
--   trial_extensions              Kaihle Admin audit trail
--
-- REMOVED (not in v2):
--   assessment_reports            → gap_states is normalised replacement
--   assessment_questions (v1)     → student_responses is the replacement
--   courses, course_sections,
--     course_question_links       → v2 curates content, does not generate courses
--   student_course_progress       → study_plan_resources.is_watched replaces this
--   study_plan_courses (v1)       → study_plan_resources + study_plan_quizzes
--   tutor_sessions, interactions  → out of scope v2.0
--   badges, student_badges        → gamification deferred
--   progress (gamification table) → deferred
--   billing_info                  → school_subscriptions replaces per-student model
--   payments, invoices (v1)       → subscription_invoices replaces these
--   roles table                   → user_role enum is sufficient
--   plan_features, plan_subjects  → subscription_plans.features JSONB
--
-- =============================================================================
