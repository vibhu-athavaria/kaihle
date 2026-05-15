"""schema_v2_2_final

Syncs ORM models with live DB for schema v2.2:
- Add updated_at to curriculum_chunks, study_plan_resources, subtopic_content_feedback
- Add gap_summary to parent_report_snapshots
- Make subtopic_content.updated_at nullable
- Add indexes on subjects.subject_family_code, subtopic_content review_status/subtopic_id
- Add FKs on subtopic_content for reviewed_by_id and teacher_explanation_author_id
- Add indexes on subtopic_content_feedback school_id and subtopic_content_id

Revision ID: 968bdc883d66
Revises: cebe6bdb5539
Create Date: 2026-05-15 08:19:30.613843

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "968bdc883d66"
down_revision: str | Sequence[str] | None = "cebe6bdb5539"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("curriculum_chunks", sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True))

    op.add_column(
        "parent_report_snapshots", sa.Column("gap_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False)
    )

    op.add_column("study_plan_resources", sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True))

    op.create_index(op.f("ix_subjects_subject_family_code"), "subjects", ["subject_family_code"], unique=False)

    op.alter_column("subtopic_content", "updated_at", nullable=True, existing_server_default=sa.text("now()"))
    op.create_index("idx_subtopic_content_explanation_status", "subtopic_content", ["review_status"], unique=False)
    op.create_index("idx_subtopic_content_subtopic", "subtopic_content", ["subtopic_id"], unique=False)
    op.create_foreign_key(None, "subtopic_content", "users", ["reviewed_by_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        None, "subtopic_content", "users", ["teacher_explanation_author_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column(
        "subtopic_content_feedback", sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True)
    )
    op.create_index(
        op.f("ix_subtopic_content_feedback_school_id"), "subtopic_content_feedback", ["school_id"], unique=False
    )
    op.create_index(
        op.f("ix_subtopic_content_feedback_subtopic_content_id"),
        "subtopic_content_feedback",
        ["subtopic_content_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_subtopic_content_feedback_subtopic_content_id"), table_name="subtopic_content_feedback")
    op.drop_index(op.f("ix_subtopic_content_feedback_school_id"), table_name="subtopic_content_feedback")
    op.drop_column("subtopic_content_feedback", "updated_at")

    op.drop_constraint(None, "subtopic_content", type_="foreignkey")
    op.drop_constraint(None, "subtopic_content", type_="foreignkey")
    op.drop_index("idx_subtopic_content_subtopic", table_name="subtopic_content")
    op.drop_index("idx_subtopic_content_explanation_status", table_name="subtopic_content")
    op.alter_column("subtopic_content", "updated_at", nullable=False, existing_server_default=sa.text("now()"))

    op.drop_index(op.f("ix_subjects_subject_family_code"), table_name="subjects")

    op.drop_column("study_plan_resources", "updated_at")

    op.drop_column("parent_report_snapshots", "gap_summary")

    op.drop_column("curriculum_chunks", "updated_at")
