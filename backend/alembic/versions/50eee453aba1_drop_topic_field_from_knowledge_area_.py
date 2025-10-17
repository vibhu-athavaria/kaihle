"""drop topic field from knowledge_area field

Revision ID: 50eee453aba1
Revises: 43091834e8ed
Create Date: 2025-10-14 17:20:51.460633

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50eee453aba1'
down_revision = '43091834e8ed'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('knowledge_areas', 'topic')


def downgrade():
    op.add_column('knowledge_areas', sa.Column('topic', sa.String(), nullable=False))

