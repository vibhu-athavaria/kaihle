"""Update topic and subtopic search

Revision ID: c2adaa6b3d68
Revises: 8607381bf6ed
Create Date: 2026-02-10 18:49:31.980419

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2adaa6b3d68'
down_revision = '8607381bf6ed'
branch_labels = None
depends_on = None


def upgrade():
    # Ensure pg_trgm extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Alter topic.name → TEXT
    op.alter_column(
        "topics",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.Text(),
        nullable=False,
    )

    # Alter subtopics.name → TEXT
    op.alter_column(
        "subtopics",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.Text(),
        nullable=False,
    )

    # Create trigram indexes for fast search
    op.create_index(
        "idx_topics_name_trgm",
        "topics",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )

    op.create_index(
        "idx_subtopics_name_trgm",
        "subtopics",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade():

    op.drop_index("idx_subtopics_name_trgm", table_name="subtopics")
    op.drop_index("idx_topics_name_trgm", table_name="topics")

    op.alter_column(
        "subtopics",
        "name",
        existing_type=sa.Text(),
        type_=sa.String(length=200),
        nullable=False,
    )

    op.alter_column(
        "topics",
        "name",
        existing_type=sa.Text(),
        type_=sa.String(length=200),
        nullable=False,
    )
