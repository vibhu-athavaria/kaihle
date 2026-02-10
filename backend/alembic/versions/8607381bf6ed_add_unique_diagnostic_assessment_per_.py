"""add unique diagnostic assessment per student subject

Revision ID: 8607381bf6ed
Revises: 25b7607b597f
Create Date: 2026-02-10 12:07:56.484392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8607381bf6ed'
down_revision = '25b7607b597f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_diagnostic_assessment_student_subject",
        "assessments",
        ["student_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("assessment_type = 'DIAGNOSTIC'")
    )


def downgrade():
    op.drop_index(
        "uq_diagnostic_assessment_student_subject",
        table_name="assessments",
        postgresql_where=sa.text("assessment_type = 'DIAGNOSTIC'")
    )
