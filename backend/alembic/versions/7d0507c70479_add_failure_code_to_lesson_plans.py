"""add failure_code to lesson_plans

Revision ID: 7d0507c70479
Revises: 077e15382ac9
Create Date: 2026-05-07

"""

from alembic import op
import sqlalchemy as sa

revision = "7d0507c70479"
down_revision = "077e15382ac9"
branch_labels = None
depends_on = None

failure_code_enum = sa.Enum(
    "llm_auth_error",
    "llm_rate_limit_error",
    "llm_connection_error",
    "llm_unexpected_error",
    "json_parse_failed",
    "class_not_found",
    name="lesson_plan_failure_code",
)


def upgrade() -> None:
    failure_code_enum.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE lesson_plans ADD COLUMN IF NOT EXISTS failure_code lesson_plan_failure_code")


def downgrade() -> None:
    op.drop_column("lesson_plans", "failure_code")
    failure_code_enum.drop(op.get_bind(), checkfirst=True)
