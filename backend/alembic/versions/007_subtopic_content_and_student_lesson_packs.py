"""Add subtopic_content and student_lesson_packs tables.

Revision ID: 007
Revises: 006
Create Date: 2025-01-01 00:00:00.000000

"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums first (if not exists —idempotent)
    op.execute("CREATE TYPE IF NOT EXISTS content_type_enum AS ENUM ('video', 'explanation', 'practice', 'quiz')")
    op.execute("CREATE TYPE IF NOT EXISTS review_status_enum AS ENUM ('pending', 'approved', 'rejected')")
    op.execute("CREATE TYPE IF NOT EXISTS pack_type_enum AS ENUM ('quiz', 'video', 'explanation', 'mixed')")
    op.execute(
        "CREATE TYPE IF NOT EXISTS pack_status_enum AS ENUM ('generated', 'sent', 'in_progress', 'completed', 'expired')"
    )

    # --- interest_categories table ---
    # Lookup table for interest categories used in content personalisation.
    # Maps to subtopic_content.interest_category_id (FK).
    op.create_table(
        "interest_categories",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Seed the 5 interest categories
    interest_category_records = [
        {"id": str(uuid.uuid4()), "name": "Adventure & Exploration"},
        {"id": str(uuid.uuid4()), "name": "Music & Arts"},
        {"id": str(uuid.uuid4()), "name": "Nature & Science"},
        {"id": str(uuid.uuid4()), "name": "Everyday Life"},
        {"id": str(uuid.uuid4()), "name": "Sports & Fitness"},
        {"id": str(uuid.uuid4()), "name": "Technology & Innovation"},
    ]
    for rec in interest_category_records:
        op.execute(
            f"INSERT INTO interest_categories (id, name) "
            f"VALUES ('{rec['id']}', '{rec['name']}') "
            f"ON CONFLICT (name) DO NOTHING"
        )

    # --- subtopic_content table ---
    # No school_id — curriculum-layer table (per CONSTITUTION Rule 2)
    op.create_table(
        "subtopic_content",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column(
            "subtopic_id",
            sa.UUID(),
            sa.ForeignKey("subtopics.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "content_type",
            sa.Enum(
                "video",
                "explanation",
                "practice",
                "quiz",
                name="content_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        # video fields (individual columns for single video per row)
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("video_provider", sa.Text(), nullable=True),
        sa.Column("video_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("video_thumbnail_url", sa.Text(), nullable=True),
        # videos JSONB array for multiple video candidates per subtopic
        # Each entry: {url, title, channel, view_count, status, last_checked_at}
        sa.Column("videos", JSONB(astext=False), nullable=True),
        # explanation fields
        sa.Column("explanation_text", sa.Text(), nullable=True),
        # practice / quiz fields — JSON array of question objects
        # each: { "question_id": str, "question_text": str, "options": [...], "correct_answer": str, "explanation": str }
        sa.Column("quiz_questions", JSONB(astext=False), nullable=True),
        sa.Column(
            "quiz_questions_count",
            sa.Integer(),
            sa.CheckConstraint("quiz_questions_count >= 0", name="ck_quiz_questions_count_positive"),
            nullable=True,
        ),
        # teacher-provided text explanation (not AI)
        sa.Column("teacher_explanation", sa.Text(), nullable=True),
        sa.Column("teacher_explanation_author_id", sa.UUID(), nullable=True),
        # Interest category for personalization
        sa.Column(
            "interest_category_id",
            sa.UUID(),
            sa.ForeignKey("interest_categories.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Tier levels this content applies to (array, e.g. [1, 2] or [1, 2, 3])
        sa.Column(
            "applicable_tiers",
            ARRAY(sa.Integer()),
            nullable=False,
            server_default="{1,2,3}",
        ),
        # Review / approval workflow
        sa.Column(
            "review_status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="review_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # Status and timestamps
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            index=True,
        ),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            index=True,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Partial unique indexes: only one active item per (subtopic, content_type)
    # Uses PostgreSQL partial unique index WHERE clause
    op.create_index(
        "uq_subtopic_content_active_video_per_subtopic",
        "subtopic_content",
        ["subtopic_id", "content_type"],
        unique=True,
        postgresql_where=sa.text("content_type = 'video' AND is_active = true AND is_archived = false"),
    )
    op.create_index(
        "uq_subtopic_content_active_explanation_per_subtopic",
        "subtopic_content",
        ["subtopic_id", "content_type"],
        unique=True,
        postgresql_where=sa.text("content_type = 'explanation' AND is_active = true AND is_archived = false"),
    )
    op.create_index(
        "uq_subtopic_content_active_practice_per_subtopic",
        "subtopic_content",
        ["subtopic_id", "content_type"],
        unique=True,
        postgresql_where=sa.text("content_type = 'practice' AND is_active = true AND is_archived = false"),
    )

    # --- student_lesson_packs table ---
    op.create_table(
        "student_lesson_packs",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column(
            "student_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "school_id",
            sa.UUID(),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # ARRAY of UUID references to subtopic_content.id
        sa.Column(
            "content_ids",
            ARRAY(sa.UUID()),
            nullable=False,
        ),
        # Denormalised subtopic UUIDs for quick lookup
        sa.Column(
            "subtopic_ids",
            ARRAY(sa.UUID()),
            nullable=False,
        ),
        # Human-readable title
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "pack_type",
            sa.Enum(
                "quiz",
                "video",
                "explanation",
                "mixed",
                name="pack_type_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="mixed",
        ),
        # Target tier (1, 2, or 3)
        sa.Column(
            "target_tier",
            sa.Integer(),
            sa.CheckConstraint("target_tier >= 1 AND target_tier <= 3", name="ck_target_tier_range"),
            nullable=False,
        ),
        # Mastery score achieved (0.0000 to 1.0000)
        sa.Column(
            "mastery_score",
            sa.Numeric(5, 4),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "generated",
                "sent",
                "in_progress",
                "completed",
                "expired",
                name="pack_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="generated",
            index=True,
        ),
        sa.Column("generated_by_teacher_id", sa.UUID(), nullable=True),
        # Expiry timestamp (used by M3-0-T3 stale-link Celery job)
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Partial index: active packs per student (not archived, not expired)
    op.create_index(
        "ix_student_lesson_packs_student_active",
        "student_lesson_packs",
        ["student_id", "status"],
        postgresql_where=sa.text("is_archived = false AND status != 'expired'"),
    )


def downgrade() -> None:
    op.drop_table("student_lesson_packs")
    op.drop_table("subtopic_content")
    op.drop_table("interest_categories")

    # Drop enums (will fail if any other objects depend on them — acceptable in dev)
    op.execute("DROP TYPE IF EXISTS pack_status_enum")
    op.execute("DROP TYPE IF EXISTS pack_type_enum")
    op.execute("DROP TYPE IF EXISTS review_status_enum")
    op.execute("DROP TYPE IF EXISTS content_type_enum")
