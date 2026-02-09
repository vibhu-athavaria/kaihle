"""Add UI fields, curriculum-subject mapping, and student curriculum

Revision ID: 287f61b46d66
Revises: 75b47ad39419
Create Date: 2026-02-06 20:22:22.418039

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '287f61b46d66'
down_revision = '75b47ad39419'
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------
    # 1. Subjects: add gradient_key
    # -------------------------------------------------
    op.add_column(
        "subjects",
        sa.Column("gradient_key", sa.String(length=50), nullable=True),
    )

    # -------------------------------------------------
    # 2. Badges: add color_key
    # -------------------------------------------------
    op.add_column(
        "badges",
        sa.Column("color_key", sa.String(length=50), nullable=True),
    )

    # -------------------------------------------------
    # 3. Curriculum ↔ Subject mapping table
    # -------------------------------------------------
    op.create_table(
        "curriculum_subjects",
        sa.Column(
            "curriculum_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("curricula.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_core",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("curriculum_id", "subject_id"),
    )

    # Helpful indexes (optional but good)
    op.create_index(
        "ix_curriculum_subjects_curriculum_id",
        "curriculum_subjects",
        ["curriculum_id"],
    )
    op.create_index(
        "ix_curriculum_subjects_subject_id",
        "curriculum_subjects",
        ["subject_id"],
    )

    # -------------------------------------------------
    # 4. Student profile: add curriculum_id
    # -------------------------------------------------
    op.add_column(
        "student_profiles",
        sa.Column(
            "curriculum_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("curricula.id"),
            nullable=True,
        ),
    )


def downgrade():
    # -------------------------------------------------
    # Reverse student_profiles change
    # -------------------------------------------------
    op.drop_column("student_profiles", "curriculum_id")

    # -------------------------------------------------
    # Drop curriculum_subjects table
    # -------------------------------------------------
    op.drop_index(
        "ix_curriculum_subjects_subject_id",
        table_name="curriculum_subjects",
    )
    op.drop_index(
        "ix_curriculum_subjects_curriculum_id",
        table_name="curriculum_subjects",
    )
    op.drop_table("curriculum_subjects")

    # -------------------------------------------------
    # Reverse badges change
    # -------------------------------------------------
    op.drop_column("badges", "color_key")

    # -------------------------------------------------
    # Reverse subjects change
    # -------------------------------------------------
    op.drop_column("subjects", "gradient_key")
