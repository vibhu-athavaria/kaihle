"""auto generate uuid for question_bank id and add unique signature index

Revision ID: 52a620c3043a
Revises: 749be2eb6620
Create Date: 2026-02-17 14:56:58.508394

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '52a620c3043a'
down_revision = '749be2eb6620'
branch_labels = None
depends_on = None


def upgrade():
    # Ensure pgcrypto extension exists (for gen_random_uuid)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Set default UUID generator for id column
    op.execute("""
        ALTER TABLE question_bank
        ALTER COLUMN id SET DEFAULT gen_random_uuid();
    """)

    # Create unique index for deduplication
    op.create_index(
        "uq_question_signature",
        "question_bank",
        ["subtopic_id", "problem_signature", "difficulty_level"],
        unique=True
    )


def downgrade():
    # Drop unique index
    op.drop_index("uq_question_signature", table_name="question_bank")

    # Remove default UUID generator
    op.execute("""
        ALTER TABLE question_bank
        ALTER COLUMN id DROP DEFAULT;
    """)