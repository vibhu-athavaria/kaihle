"""make subtopics grade aware via curriculum_topic

Revision ID: b10d7cca7994
Revises: c2adaa6b3d68
Create Date: 2026-02-11 15:57:07.947251

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b10d7cca7994'
down_revision = 'c2adaa6b3d68'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new column
    op.add_column(
        "subtopics",
        sa.Column(
            "curriculum_topic_id",
            postgresql.UUID(as_uuid=True),
            nullable=True
        )
    )

    # 2. Add FK constraint
    op.create_foreign_key(
        "fk_subtopics_curriculum_topic",
        "subtopics",
        "curriculum_topics",
        ["curriculum_topic_id"],
        ["id"],
        ondelete="CASCADE"
    )

    # 3. Data migration:
    # Map old topic_id to curriculum_topic_id
    op.execute("""
        UPDATE subtopics s
        SET curriculum_topic_id = ct.id
        FROM curriculum_topics ct
        WHERE s.topic_id = ct.topic_id
    """)

    # 4. Make column NOT NULL
    op.alter_column("subtopics", "curriculum_topic_id", nullable=False)

    # 5. Drop old FK and column
    op.drop_constraint("subtopics_topic_id_fkey", "subtopics", type_="foreignkey")
    op.drop_column("subtopics", "topic_id")


def downgrade():
    # Reverse everything if needed
    op.add_column(
        "subtopics",
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            nullable=True
        )
    )

    op.execute("""
        UPDATE subtopics s
        SET topic_id = ct.topic_id
        FROM curriculum_topics ct
        WHERE s.curriculum_topic_id = ct.id
    """)

    op.alter_column("subtopics", "topic_id", nullable=False)

    op.drop_constraint("fk_subtopics_curriculum_topic", "subtopics", type_="foreignkey")
    op.drop_column("subtopics", "curriculum_topic_id")
