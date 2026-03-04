"""Initial schema - all 35 tables for Kaihle v2.1

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-04

"""
from collections.abc import Sequence

import sqlalchemy as sa

# Use sqlalchemy.types.UserDefinedType for VECTOR
from sqlalchemy import types
from sqlalchemy.dialects import postgresql

from alembic import op


class Vector(types.UserDefinedType):
    cache_ok = True

    def __init__(self, dimension=768):
        self.dimension = dimension

    def get_col_spec(self):
        return f'Vector({self.dimension})'

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(postgresql.ARRAY(sa.Float, dimensions=2))

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # EXTENSIONS
    # =========================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # =========================================================================
    # ENUMS (14 types)
    # =========================================================================

    # assessment_type
    assessment_type = postgresql.ENUM(
        'DIAGNOSTIC', 'TOPIC_SPECIFIC', 'PROGRESS_CHECK', 'FINAL',
        name='assessment_type', create_type=False
    )
    assessment_type.create(op.get_bind(), checkfirst=True)

    # assessment_status
    assessment_status = postgresql.ENUM(
        'DRAFT', 'ACTIVE', 'CLOSED',
        name='assessment_status', create_type=False
    )
    assessment_status.create(op.get_bind(), checkfirst=True)

    # attempt_status
    attempt_status = postgresql.ENUM(
        'NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED',
        name='attempt_status', create_type=False
    )
    attempt_status.create(op.get_bind(), checkfirst=True)

    # question_type
    question_type = postgresql.ENUM(
        'MCQ', 'TRUE_FALSE', 'SHORT_ANSWER',
        name='question_type', create_type=False
    )
    question_type.create(op.get_bind(), checkfirst=True)

    # scored_by
    scored_by = postgresql.ENUM(
        'RULE', 'LLM', 'PENDING',
        name='scored_by', create_type=False
    )
    scored_by.create(op.get_bind(), checkfirst=True)

    # study_plan_status
    study_plan_status = postgresql.ENUM(
        'GENERATING', 'ACTIVE', 'COMPLETED', 'ABANDONED',
        name='study_plan_status', create_type=False
    )
    study_plan_status.create(op.get_bind(), checkfirst=True)

    # resource_type
    resource_type = postgresql.ENUM(
        'VIDEO', 'ARTICLE', 'INTERACTIVE',
        name='resource_type', create_type=False
    )
    resource_type.create(op.get_bind(), checkfirst=True)

    # lesson_plan_status
    lesson_plan_status = postgresql.ENUM(
        'GENERATED', 'EDITED', 'USED', 'ARCHIVED',
        name='lesson_plan_status', create_type=False
    )
    lesson_plan_status.create(op.get_bind(), checkfirst=True)

    # subscription_tier
    subscription_tier = postgresql.ENUM(
        'TRIAL', 'STARTER', 'GROWTH', 'SCALE',
        name='subscription_tier', create_type=False
    )
    subscription_tier.create(op.get_bind(), checkfirst=True)

    # subscription_status
    subscription_status = postgresql.ENUM(
        'ACTIVE', 'PAST_DUE', 'CANCELLED', 'EXPIRED',
        name='subscription_status', create_type=False
    )
    subscription_status.create(op.get_bind(), checkfirst=True)

    # payment_status
    payment_status = postgresql.ENUM(
        'PENDING', 'PAID', 'FAILED', 'REFUNDED',
        name='payment_status', create_type=False
    )
    payment_status.create(op.get_bind(), checkfirst=True)

    # user_role
    user_role = postgresql.ENUM(
        'STUDENT', 'TEACHER', 'SCHOOL_ADMIN', 'PARENT', 'KAIHLE_ADMIN',
        name='user_role', create_type=False
    )
    user_role.create(op.get_bind(), checkfirst=True)

    # auth_token_type
    auth_token_type = postgresql.ENUM(
        'MAGIC_LINK', 'REFRESH',
        name='auth_token_type', create_type=False
    )
    auth_token_type.create(op.get_bind(), checkfirst=True)

    # onboarding_status
    onboarding_status = postgresql.ENUM(
        'PENDING', 'IN_PROGRESS', 'COMPLETED',
        name='onboarding_status', create_type=False
    )
    onboarding_status.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # SECTION 1: CURRICULUM LAYER (school-agnostic tables)
    # =========================================================================

    # curricula
    op.create_table(
        'curricula',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('country', sa.String(100)),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint('code', name='curricula_code_key'),
        sa.UniqueConstraint('name', name='curricula_name_key'),
        comment='Global curriculum boards. School-agnostic.'
    )

    # subjects
    op.create_table(
        'subjects',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('icon', sa.String(50)),
        sa.Column('color', sa.String(7)),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint('code', name='subjects_code_key'),
        sa.UniqueConstraint('name', name='subjects_name_key'),
        comment='Global subject catalogue. School-agnostic.'
    )

    # grades
    op.create_table(
        'grades',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint('level', name='grades_level_key'),
        sa.CheckConstraint('level BETWEEN 1 AND 13', name='grades_level_range'),
        comment='Global grade levels. School-agnostic.'
    )

    # topics
    op.create_table(
        'topics',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('canonical_code', sa.String(50)),
        sa.Column('description', sa.Text()),
        sa.Column('keywords', postgresql.ARRAY(sa.Text())),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True))
    )
    op.create_index('idx_topics_canonical_code', 'topics', ['canonical_code'])

    # curriculum_subjects
    op.create_table(
        'curriculum_subjects',
        sa.Column('curriculum_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('is_core', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer()),
        sa.ForeignKeyConstraint(['curriculum_id'], ['curricula.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('curriculum_id', 'subject_id'),
        comment='Which subjects belong to a curriculum.'
    )

    # curriculum_topics
    op.create_table(
        'curriculum_topics',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('curriculum_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('grade_id', sa.UUID(), nullable=False),
        sa.Column('topic_id', sa.UUID(), nullable=False),
        sa.Column('standard_code', sa.String(100)),
        sa.Column('sequence_order', sa.Integer()),
        sa.Column('learning_objectives', postgresql.ARRAY(sa.Text())),
        sa.Column('recommended_weeks', sa.Integer()),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['curriculum_id'], ['curricula.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('curriculum_id', 'subject_id', 'grade_id', 'topic_id', name='curriculum_topics_unique'),
        sa.CheckConstraint('sequence_order IS NULL OR sequence_order > 0', name='chk_ct_sequence'),
        comment='The pivot table binding curriculum + subject + grade + topic.'
    )
    op.create_index('idx_ct_curriculum_subject_grade', 'curriculum_topics', ['curriculum_id', 'subject_id', 'grade_id'])
    op.create_index('idx_ct_topic', 'curriculum_topics', ['topic_id'])

    # subtopics
    op.create_table(
        'subtopics',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('curriculum_topic_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('canonical_code', sa.String(50)),
        sa.Column('description', sa.Text()),
        sa.Column('learning_objective', sa.Text(), nullable=False),
        sa.Column('keywords', postgresql.ARRAY(sa.Text())),
        sa.Column('bloom_taxonomy_level', sa.String(50)),
        sa.Column('difficulty_level', sa.Integer()),
        sa.Column('estimated_minutes', sa.Integer()),
        sa.Column('sequence_order', sa.Integer()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('embedding', Vector(768)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['curriculum_topic_id'], ['curriculum_topics.id'], ondelete='CASCADE'),
        sa.CheckConstraint('difficulty_level IS NULL OR difficulty_level BETWEEN 1 AND 5', name='chk_subtopic_difficulty'),
        comment='Atomic unit of knowledge.'
    )
    op.create_index('idx_subtopics_curriculum_topic', 'subtopics', ['curriculum_topic_id'])
    op.create_index('idx_subtopics_canonical_code', 'subtopics', ['canonical_code'])
    # Deferred: ivfflat index requires data - add comment for later
    # op.execute("COMMENT ON INDEX idx_subtopics_embedding IS 'Requires data load: CREATE INDEX idx_subtopics_embedding ON subtopics USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'")

    # subtopic_prerequisites
    op.create_table(
        'subtopic_prerequisites',
        sa.Column('subtopic_id', sa.UUID(), nullable=False),
        sa.Column('prerequisite_subtopic_id', sa.UUID(), nullable=False),
        sa.Column('importance', sa.String(20), nullable=False, server_default='REQUIRED'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subtopic_id'], ['subtopics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prerequisite_subtopic_id'], ['subtopics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('subtopic_id', 'prerequisite_subtopic_id'),
        sa.CheckConstraint('subtopic_id <> prerequisite_subtopic_id', name='chk_no_self_prereq'),
        sa.CheckConstraint("importance IN ('REQUIRED', 'RECOMMENDED', 'HELPFUL')", name='chk_importance'),
        comment='Prerequisite graph at subtopic level.'
    )

    # curriculum_chunks
    op.create_table(
        'curriculum_chunks',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subtopic_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer()),
        sa.Column('source_file', sa.String(255)),
        sa.Column('page_number', sa.Integer()),
        sa.Column('embedding', Vector(768)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subtopic_id'], ['subtopics.id'], ondelete='CASCADE'),
        sa.CheckConstraint('chunk_index >= 0', name='chk_chunk_index'),
        comment='Text chunks extracted from curriculum PDF files, linked to subtopics.'
    )
    op.create_index('idx_chunks_subtopic', 'curriculum_chunks', ['subtopic_id'])
    # Deferred: ivfflat index requires data

    # =========================================================================
    # SECTION 2: QUESTION BANK
    # =========================================================================

    op.create_table(
        'question_bank',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subtopic_id', sa.UUID(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', question_type, nullable=False),
        sa.Column('options', postgresql.JSONB),
        sa.Column('correct_answer', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text()),
        sa.Column('hints', postgresql.JSONB),
        sa.Column('difficulty_level', sa.Float()),
        sa.Column('bloom_taxonomy_level', sa.String(50)),
        sa.Column('estimated_time_seconds', sa.Integer()),
        sa.Column('learning_objectives', postgresql.ARRAY(sa.Text())),
        sa.Column('canonical_form', sa.Text(), nullable=False),
        sa.Column('problem_signature', postgresql.JSONB, nullable=False),
        sa.Column('source', sa.String(10), nullable=False, server_default='bank'),
        sa.Column('meta_tags', postgresql.JSONB),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['subtopic_id'], ['subtopics.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('difficulty_level IS NULL OR difficulty_level BETWEEN 1.0 AND 5.0', name='chk_qb_difficulty'),
        sa.CheckConstraint("source IN ('bank', 'llm')", name='chk_qb_source'),
        comment='Single canonical question store.'
    )
    op.create_index('idx_qb_subtopic', 'question_bank', ['subtopic_id'])
    op.create_index('idx_qb_type', 'question_bank', ['question_type'])
    op.create_index('idx_qb_difficulty', 'question_bank', ['difficulty_level'])
    op.create_index('idx_qb_active', 'question_bank', ['is_active'])
    op.create_index('idx_qb_source', 'question_bank', ['source'])
    op.create_index('idx_qb_text_trgm', 'question_bank', ['question_text'], postgresql_using='gin', postgresql_ops={'question_text': 'gin_trgm_ops'})

    # =========================================================================
    # SECTION 3: SCHOOL & USER MANAGEMENT
    # =========================================================================

    # schools
    op.create_table(
        'schools',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('address', sa.String(500)),
        sa.Column('city', sa.String(100)),
        sa.Column('country', sa.String(100)),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Singapore'),
        sa.Column('contact_email', sa.String(255)),
        sa.Column('contact_phone', sa.String(50)),
        sa.Column('website', sa.String(255)),
        sa.Column('logo_url', sa.String(500)),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint('slug', name='schools_slug_key'),
        sa.CheckConstraint("status IN ('pending', 'active', 'suspended')", name='chk_school_status'),
        comment='One row per tenant. This is the multi-tenancy anchor.'
    )
    op.create_index('idx_schools_status', 'schools', ['status'])

    # school_curricula
    op.create_table(
        'school_curricula',
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('curriculum_id', sa.UUID(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('adopted_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['curriculum_id'], ['curricula.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('school_id', 'curriculum_id'),
        comment='Which curricula a school offers.'
    )
    op.create_index('idx_school_curricula_one_primary', 'school_curricula', ['school_id'], unique=True, postgresql_where=sa.text('is_primary = TRUE'))

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255)),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('role', user_role, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('email', name='users_email_unique'),
        comment='All human users across all roles.'
    )
    op.create_index('idx_users_school_role', 'users', ['school_id', 'role'])
    op.create_index('idx_users_email', 'users', ['email'])

    # auth_tokens
    op.create_table(
        'auth_tokens',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('type', auth_token_type, nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('token_hash', name='auth_tokens_hash_unique'),
        comment='Magic link and refresh token storage.'
    )
    op.create_index('idx_auth_tokens_user', 'auth_tokens', ['user_id'])
    op.create_index('idx_auth_tokens_expires', 'auth_tokens', ['expires_at'])

    # parent_student
    op.create_table(
        'parent_student',
        sa.Column('parent_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('parent_id', 'student_id'),
        sa.CheckConstraint('parent_id <> student_id', name='chk_ps_not_same'),
        comment='Explicit many-to-many link: parent → child students.'
    )

    # student_profiles (v2.1: added onboarding_diagnostic_status)
    op.create_table(
        'student_profiles',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('grade_id', sa.UUID()),
        sa.Column('age', sa.Integer()),
        sa.Column('onboarding_diagnostic_status', onboarding_status, nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('user_id', name='sp_user_unique'),
        comment='Extended profile for student users.'
    )

    # teacher_profiles
    op.create_table(
        'teacher_profiles',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('qualifications', postgresql.JSONB),
        sa.Column('experience_years', sa.Integer()),
        sa.Column('bio', sa.Text()),
        sa.Column('hire_date', sa.Date()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='tp_user_unique'),
        comment='Extended teacher data.'
    )

    # student_learning_profiles (NEW v2.1)
    op.create_table(
        'student_learning_profiles',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('modality_scores', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('work_style', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('interests', postgresql.ARRAY(sa.Text())),
        sa.Column('questionnaire_version', sa.String(10), nullable=False, server_default='v1'),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('student_id', name='slp_student_unique'),
        comment='Normalised learning profile collected during student onboarding.'
    )
    op.create_index('idx_slp_student', 'student_learning_profiles', ['student_id'], unique=True)
    op.create_index('idx_slp_school', 'student_learning_profiles', ['school_id'])

    # classes
    op.create_table(
        'classes',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('grade_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('curriculum_id', sa.UUID(), nullable=False),
        sa.Column('teacher_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('academic_year', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['curriculum_id'], ['curricula.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='RESTRICT'),
        comment='Operational unit: one class = one teacher + one subject + one curriculum + one grade.'
    )
    op.create_index('idx_classes_school', 'classes', ['school_id'])
    op.create_index('idx_classes_teacher', 'classes', ['teacher_id'])
    op.create_index('idx_classes_active', 'classes', ['school_id', 'is_active'])

    # class_enrollments
    op.create_table(
        'class_enrollments',
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('enrolled_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('class_id', 'student_id'),
        comment='Many-to-many: students enrolled in classes.'
    )
    op.create_index('idx_enrollments_student', 'class_enrollments', ['student_id'])
    op.create_index('idx_enrollments_active', 'class_enrollments', ['class_id', 'is_active'])

    # =========================================================================
    # SECTION 4: ASSESSMENTS
    # =========================================================================

    # assessments (v2.1: added is_system_generated)
    op.create_table(
        'assessments',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('assessment_type', assessment_type, nullable=False),
        sa.Column('status', assessment_status, nullable=False, server_default='DRAFT'),
        sa.Column('is_system_generated', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('curriculum_topic_id', sa.UUID()),
        sa.Column('config', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('instructions', sa.Text()),
        sa.Column('due_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['curriculum_topic_id'], ['curriculum_topics.id'], ondelete='SET NULL'),
        comment='Assessment definition. Teacher creates once (Tier 2) or system creates (Tier 1).'
    )
    op.create_index('idx_assessments_class', 'assessments', ['class_id'])
    op.create_index('idx_assessments_status', 'assessments', ['status'])
    op.create_index('idx_assessments_type', 'assessments', ['assessment_type'])

    # assessment_selected_questions
    op.create_table(
        'assessment_selected_questions',
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['question_bank.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('assessment_id', 'question_id'),
        sa.CheckConstraint('order_index >= 0', name='chk_asq_order'),
        comment='Bridge between assessment definition and question_bank.'
    )
    op.create_index('idx_asq_assessment', 'assessment_selected_questions', ['assessment_id'])

    # student_attempts
    op.create_table(
        'student_attempts',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('status', attempt_status, nullable=False, server_default='NOT_STARTED'),
        sa.Column('total_questions', sa.Integer()),
        sa.Column('questions_answered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overall_score', sa.Float()),
        sa.Column('time_taken_seconds', sa.Integer()),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('assessment_id', 'student_id', name='sa_unique'),
        comment='Per-student attempt.'
    )
    op.create_index('idx_attempts_assessment', 'student_attempts', ['assessment_id'])
    op.create_index('idx_attempts_student', 'student_attempts', ['student_id'])
    op.create_index('idx_attempts_status', 'student_attempts', ['status'])

    # student_responses
    op.create_table(
        'student_responses',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('attempt_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('answer_given', sa.Text()),
        sa.Column('is_correct', sa.Boolean()),
        sa.Column('score', sa.Float()),
        sa.Column('scored_by', scored_by, nullable=False, server_default='PENDING'),
        sa.Column('ai_feedback', sa.Text()),
        sa.Column('hints_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('time_taken_ms', sa.Integer()),
        sa.Column('answered_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['attempt_id'], ['student_attempts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['question_bank.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('attempt_id', 'question_id', name='sr_unique'),
        sa.CheckConstraint('score IS NULL OR score BETWEEN 0.0 AND 1.0', name='chk_sr_score'),
        comment='Per-question response within an attempt.'
    )
    op.create_index('idx_responses_attempt', 'student_responses', ['attempt_id'])
    op.create_index('idx_responses_question', 'student_responses', ['question_id'])
    op.create_index('idx_responses_scored', 'student_responses', ['scored_by'], postgresql_where=sa.text("scored_by = 'PENDING'"))

    # =========================================================================
    # SECTION 5: GAP STATES
    # =========================================================================

    op.create_table(
        'gap_states',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('subtopic_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('mastery_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_attempted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('needs_review', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_assessed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subtopic_id'], ['subtopics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('student_id', 'subtopic_id', 'class_id', name='gap_states_unique'),
        sa.CheckConstraint('mastery_score BETWEEN 0.0 AND 1.0', name='chk_gs_mastery'),
        sa.CheckConstraint('confidence BETWEEN 0.0 AND 1.0', name='chk_gs_confidence'),
        sa.CheckConstraint('total_correct <= total_attempted', name='chk_gs_counts'),
        comment='Normalised mastery tracking.'
    )
    op.create_index('idx_gap_states_student', 'gap_states', ['student_id'])
    op.create_index('idx_gap_states_subtopic', 'gap_states', ['subtopic_id'])
    op.create_index('idx_gap_states_class', 'gap_states', ['class_id'])
    op.create_index('idx_gap_states_student_class', 'gap_states', ['student_id', 'class_id'])
    op.create_index('idx_gap_states_mastery', 'gap_states', ['mastery_score'])

    # =========================================================================
    # SECTION 6: STUDY PLANS
    # =========================================================================

    op.create_table(
        'study_plans',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('subtopic_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('assigned_by', sa.UUID(), nullable=False),
        sa.Column('status', study_plan_status, nullable=False, server_default='GENERATING'),
        sa.Column('assigned_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subtopic_id'], ['subtopics.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='RESTRICT'),
        comment='One study plan per student per subtopic per class.'
    )
    op.create_index('idx_study_plans_student', 'study_plans', ['student_id'])
    op.create_index('idx_study_plans_subtopic', 'study_plans', ['subtopic_id'])
    op.create_index('idx_study_plans_class', 'study_plans', ['class_id'])

    # study_plan_resources
    op.create_table(
        'study_plan_resources',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('resource_type', resource_type, nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('duration_seconds', sa.Integer()),
        sa.Column('alignment_score', sa.Float()),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('is_watched', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('watched_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['plan_id'], ['study_plans.id'], ondelete='CASCADE'),
        sa.CheckConstraint('alignment_score IS NULL OR alignment_score BETWEEN 0.0 AND 1.0', name='chk_spr_alignment'),
        comment='Curated external resources (2-3 per plan) sourced by content_curator.'
    )
    op.create_index('idx_spr_plan', 'study_plan_resources', ['plan_id'])

    # study_plan_quizzes
    op.create_table(
        'study_plan_quizzes',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('questions', postgresql.JSONB, nullable=False),
        sa.Column('student_answers', postgresql.JSONB),
        sa.Column('score', sa.Float()),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['plan_id'], ['study_plans.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('plan_id', name='spq_plan_unique'),
        sa.CheckConstraint('score IS NULL OR score BETWEEN 0.0 AND 1.0', name='chk_spq_score'),
        comment='AI-generated quiz. One quiz per study plan.'
    )

    # =========================================================================
    # SECTION 7: TEACHER COPILOT — LESSON PLANS
    # =========================================================================

    op.create_table(
        'lesson_plans',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('teacher_id', sa.UUID(), nullable=False),
        sa.Column('week_start', sa.Date, nullable=False),
        sa.Column('focus_subtopic_ids', postgresql.ARRAY(sa.UUID), nullable=False, server_default='{}'),
        sa.Column('gap_summary', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('generated_plan', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('teacher_edits', postgresql.JSONB),
        sa.Column('status', lesson_plan_status, nullable=False, server_default='GENERATED'),
        sa.Column('generated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('class_id', 'week_start', name='lp_class_week_unique'),
        comment='Weekly AI-generated lesson plan per class.'
    )
    op.create_index('idx_lesson_plans_class', 'lesson_plans', ['class_id'])
    op.create_index('idx_lesson_plans_teacher', 'lesson_plans', ['teacher_id'])
    op.create_index('idx_lesson_plans_week', 'lesson_plans', ['week_start'])

    # =========================================================================
    # SECTION 8: PARENT PORTAL
    # =========================================================================

    op.create_table(
        'parent_report_snapshots',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('week_start', sa.Date, nullable=False),
        sa.Column('narrative', sa.Text, nullable=False),
        sa.Column('improvements', postgresql.JSONB),
        sa.Column('needs_work', postgresql.JSONB),
        sa.Column('email_sent_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('generated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('student_id', 'week_start', name='prp_student_week_unique'),
        comment='Weekly parent narrative.'
    )
    op.create_index('idx_parent_reports_student', 'parent_report_snapshots', ['student_id'])
    op.create_index('idx_parent_reports_week', 'parent_report_snapshots', ['week_start'])

    # =========================================================================
    # SECTION 9: BILLING (per-school)
    # =========================================================================

    # subscription_plans
    op.create_table(
        'subscription_plans',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tier', subscription_tier, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('price_per_student_annual', sa.Numeric(10, 2), nullable=False),
        sa.Column('max_students', sa.Integer()),
        sa.Column('trial_days', sa.Integer()),
        sa.Column('max_curricula', sa.Integer()),
        sa.Column('features', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint('tier', name='sp_tier_unique'),
        comment='Pricing tier definitions.'
    )

    # school_subscriptions
    op.create_table(
        'school_subscriptions',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('status', subscription_status, nullable=False, server_default='ACTIVE'),
        sa.Column('billing_cycle', sa.String(20), nullable=False, server_default='annual'),
        sa.Column('student_count', sa.Integer(), nullable=False),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.CHAR(3), nullable=False, server_default='USD'),
        sa.Column('start_date', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('end_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('trial_end_date', sa.TIMESTAMP(timezone=True)),
        sa.Column('payment_status', payment_status, nullable=False, server_default='PENDING'),
        sa.Column('external_ref', sa.String(200)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ondelete='RESTRICT'),
        comment='Per-school subscription.'
    )
    op.create_index('idx_school_sub_school', 'school_subscriptions', ['school_id'])
    op.create_index('idx_school_sub_status', 'school_subscriptions', ['status'])

    # subscription_invoices
    op.create_table(
        'subscription_invoices',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subscription_id', sa.UUID(), nullable=False),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('invoice_number', sa.String(50), nullable=False),
        sa.Column('period_start', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('period_end', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('student_count', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.CHAR(3), nullable=False, server_default='USD'),
        sa.Column('status', payment_status, nullable=False, server_default='PENDING'),
        sa.Column('due_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('paid_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('pdf_url', sa.String(500)),
        sa.Column('external_ref', sa.String(200)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(['subscription_id'], ['school_subscriptions.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('invoice_number', name='inv_number_unique'),
        comment='One invoice per billing cycle per school.'
    )
    op.create_index('idx_invoices_school', 'subscription_invoices', ['school_id'])
    op.create_index('idx_invoices_subscription', 'subscription_invoices', ['subscription_id'])
    op.create_index('idx_invoices_status', 'subscription_invoices', ['status'])

    # trial_extensions
    op.create_table(
        'trial_extensions',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subscription_id', sa.UUID(), nullable=False),
        sa.Column('extended_by_admin_id', sa.UUID(), nullable=False),
        sa.Column('original_trial_end', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('new_trial_end', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('extension_days', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subscription_id'], ['school_subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extended_by_admin_id'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('extension_days > 0', name='chk_te_days'),
        sa.CheckConstraint('new_trial_end > original_trial_end', name='chk_te_direction'),
        comment='Audit trail for trial extensions granted by Kaihle Admin.'
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('trial_extensions')
    op.drop_table('subscription_invoices')
    op.drop_table('school_subscriptions')
    op.drop_table('subscription_plans')
    op.drop_table('parent_report_snapshots')
    op.drop_table('lesson_plans')
    op.drop_table('study_plan_quizzes')
    op.drop_table('study_plan_resources')
    op.drop_table('study_plans')
    op.drop_table('gap_states')
    op.drop_table('student_responses')
    op.drop_table('student_attempts')
    op.drop_table('assessment_selected_questions')
    op.drop_table('assessments')
    op.drop_table('class_enrollments')
    op.drop_table('classes')
    op.drop_table('student_learning_profiles')
    op.drop_table('teacher_profiles')
    op.drop_table('student_profiles')
    op.drop_table('parent_student')
    op.drop_table('auth_tokens')
    op.drop_table('users')
    op.drop_table('school_curricula')
    op.drop_table('schools')
    op.drop_table('question_bank')
    op.drop_table('curriculum_chunks')
    op.drop_table('subtopic_prerequisites')
    op.drop_table('subtopics')
    op.drop_table('curriculum_topics')
    op.drop_table('curriculum_subjects')
    op.drop_table('topics')
    op.drop_table('grades')
    op.drop_table('subjects')
    op.drop_table('curricula')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS onboarding_status')
    op.execute('DROP TYPE IF EXISTS auth_token_type')
    op.execute('DROP TYPE IF EXISTS user_role')
    op.execute('DROP TYPE IF EXISTS payment_status')
    op.execute('DROP TYPE IF EXISTS subscription_status')
    op.execute('DROP TYPE IF EXISTS subscription_tier')
    op.execute('DROP TYPE IF EXISTS lesson_plan_status')
    op.execute('DROP TYPE IF EXISTS resource_type')
    op.execute('DROP TYPE IF EXISTS study_plan_status')
    op.execute('DROP TYPE IF EXISTS scored_by')
    op.execute('DROP TYPE IF EXISTS question_type')
    op.execute('DROP TYPE IF EXISTS attempt_status')
    op.execute('DROP TYPE IF EXISTS assessment_status')
    op.execute('DROP TYPE IF EXISTS assessment_type')

    # Extensions are not dropped as they may be used by other things
    # op.execute('DROP EXTENSION IF EXISTS vector')
    # op.execute('DROP EXTENSION IF EXISTS pg_trgm')
    # op.execute('DROP EXTENSION IF EXISTS pgcrypto')
