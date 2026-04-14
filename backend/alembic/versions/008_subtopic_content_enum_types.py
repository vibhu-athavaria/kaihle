"""Convert subtopic_content columns to PostgreSQL enum types.

Revision ID: 008
Revises: c1156cdb4c15
Create Date: 2026-04-14 06:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop partial indexes (WHERE predicates reference content_type enum)
    op.drop_index("uq_subtopic_content_active_video_per_subtopic", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_active_explanation_per_subtopic", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_active_practice_per_subtopic", table_name="subtopic_content")

    # 2. Drop column defaults (server_default binds to the enum type)
    op.execute("ALTER TABLE subtopic_content ALTER COLUMN content_type DROP DEFAULT")
    op.execute("ALTER TABLE subtopic_content ALTER COLUMN review_status DROP DEFAULT")

    # 3. Demote columns to VARCHAR (now safe — no indexes or defaults blocking)
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN content_type TYPE VARCHAR(20)
        USING content_type::text
    """)
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN review_status TYPE VARCHAR(20)
        USING review_status::text
    """)

    # 4. Drop old _enum-suffixed types (nothing depends on them now)
    op.execute("DROP TYPE IF EXISTS content_type_enum")
    op.execute("DROP TYPE IF EXISTS review_status_enum")

    # 5. Create clean enum types (no _enum suffix)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'content_type') THEN
                CREATE TYPE content_type AS ENUM ('video', 'explanation', 'practice', 'quiz');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status') THEN
                CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected');
            END IF;
        END $$;
    """)

    # 6. Promote columns back to clean enum types
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN content_type TYPE content_type
        USING content_type::content_type
    """)
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN review_status TYPE review_status
        USING review_status::review_status
    """)

    # 7. Restore column defaults against the new types
    op.execute("ALTER TABLE subtopic_content ALTER COLUMN review_status SET DEFAULT 'pending'")

    # 8. Recreate partial indexes against the clean enum type
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


def downgrade() -> None:
    # 1. Drop partial indexes
    op.drop_index("uq_subtopic_content_active_video_per_subtopic", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_active_explanation_per_subtopic", table_name="subtopic_content")
    op.drop_index("uq_subtopic_content_active_practice_per_subtopic", table_name="subtopic_content")

    # 2. Drop column defaults (bound to the new clean enum types)
    op.execute("ALTER TABLE subtopic_content ALTER COLUMN content_type DROP DEFAULT")
    op.execute("ALTER TABLE subtopic_content ALTER COLUMN review_status DROP DEFAULT")

    # 3. Demote columns to VARCHAR
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN content_type TYPE VARCHAR(20)
        USING content_type::text
    """)
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN review_status TYPE VARCHAR(20)
        USING review_status::text
    """)

    # 4. Drop the clean enum types (nothing depends on them now)
    op.execute("DROP TYPE IF EXISTS content_type")
    op.execute("DROP TYPE IF EXISTS review_status")

    # 5. Recreate the original _enum-suffixed types
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'content_type_enum') THEN
                CREATE TYPE content_type_enum AS ENUM ('video', 'explanation', 'practice', 'quiz');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status_enum') THEN
                CREATE TYPE review_status_enum AS ENUM ('pending', 'approved', 'rejected');
            END IF;
        END $$;
    """)

    # 6. Promote columns back to the original _enum types
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN content_type TYPE content_type_enum
        USING content_type::content_type_enum
    """)
    op.execute("""
        ALTER TABLE subtopic_content
        ALTER COLUMN review_status TYPE review_status_enum
        USING review_status::review_status_enum
    """)

    # 7. Restore original server_default
    op.execute("ALTER TABLE subtopic_content ALTER COLUMN review_status SET DEFAULT 'pending'")

    # 8. Recreate partial indexes against the restored _enum type
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
