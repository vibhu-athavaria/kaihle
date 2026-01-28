"""add curriculum mapping tables

Revision ID: 792e00593eac
Revises: 71bfcaf277f8
Create Date: 2026-01-19 15:10:18.397602

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '792e00593eac'
down_revision = '71bfcaf277f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Curriculum Provider Table ###
    op.create_table('curriculum',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('code')
    )

    # ### Grade Table ###
    op.create_table('grade',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('level')
    )

    # ### Subject Table ###
    op.create_table('subject',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # ### Topic Table ###
    op.create_table('topic',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('canonical_code', sa.Text(), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('learning_objectives', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_topic_difficulty_level')
    )

    # ### Topic Prerequisites Table ###
    op.create_table('topic_prerequisite',
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('prerequisite_topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['topic_id'], ['topic.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prerequisite_topic_id'], ['topic.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('topic_id', 'prerequisite_topic_id'),
        sa.CheckConstraint('topic_id <> prerequisite_topic_id', name='chk_no_self_prereq')
    )

    # ### Curriculum Topic Mapping Table ###
    op.create_table('curriculum_topic',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('curriculum_id', sa.Integer(), nullable=False),
        sa.Column('grade_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('sequence_order', sa.Integer(), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('learning_objectives', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['curriculum_id'], ['curriculum.id']),
        sa.ForeignKeyConstraint(['grade_id'], ['grade.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subject.id']),
        sa.ForeignKeyConstraint(['topic_id'], ['topic.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('curriculum_id', 'grade_id', 'subject_id', 'topic_id'),
        sa.CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_curriculum_topic_difficulty_level')
    )

    # ### Subtopic Table ###
    op.create_table('subtopic',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('curriculum_topic_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_order', sa.Integer(), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('learning_objectives', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['curriculum_topic_id'], ['curriculum_topic.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('difficulty_level BETWEEN 1 AND 5', name='chk_subtopic_difficulty_level')
    )

    # ### Indexes for Performance ###
    op.create_index('idx_curriculum_topic_lookup', 'curriculum_topic', ['curriculum_id', 'grade_id', 'subject_id'], unique=False)
    op.create_index('idx_topic_prerequisite_topic', 'topic_prerequisite', ['topic_id'], unique=False)
    op.create_index('idx_topic_prerequisite_prereq', 'topic_prerequisite', ['prerequisite_topic_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_topic_prerequisite_prereq', table_name='topic_prerequisite')
    op.drop_index('idx_topic_prerequisite_topic', table_name='topic_prerequisite')
    op.drop_index('idx_curriculum_topic_lookup', table_name='curriculum_topic')

    # Drop tables in reverse order
    op.drop_table('subtopic')
    op.drop_table('curriculum_topic')
    op.drop_table('topic_prerequisite')
    op.drop_table('topic')
    op.drop_table('subject')
    op.drop_table('grade')
    op.drop_table('curriculum')
